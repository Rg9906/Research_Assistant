import logging
import threading
from functools import lru_cache
from typing import Dict, List
from uuid import UUID

from llama_index.core.llms import ChatMessage
from paperpilot.config import get_settings
from paperpilot.llm import LLMConfigurationError, build_chat_model
from paperpilot.workspace.manager import WorkspaceManager
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.agent.comparison import ComparisonAgent
from paperpilot.agent.critic import CriticAgent
from paperpilot.agent.tutor import TutorAgent
from paperpilot.services.comparison import ComparisonService
from paperpilot.services.grounded_qa import GroundedQAService
from paperpilot.services.summarizer import SummarizerService
from paperpilot.search.agent import SearchAgent
from paperpilot.search.ranker import PaperRanker
from paperpilot.search.providers import ArxivProvider, SemanticScholarProvider
from paperpilot.services.paper_chat import PaperSessionManager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class WorkspaceChatStore:
    """Write-through cache of per-workspace chat memory, backed by the workspace DB.

    PaperSession no longer holds conversation state itself (a single cached
    session is shared by every workspace/user asking about the same paper —
    see paperpilot.services.paper_chat.session._build_chat_engine), so
    something above it must own "which messages belong to this
    conversation." A workspace is the unit of conversation the API exposes
    (`/api/workspaces/{id}/chat`), so history is scoped by workspace_id here.

    Originally this was a bare in-memory dict, so history did not survive a
    server restart. It now writes through to WorkspaceManager's
    `chat_messages` table on every `set()`, so a conversation outlives the
    process; the in-memory dict remains as a read cache so a hot workspace
    doesn't re-hit the DB on every turn. `get`/`set` signatures are unchanged
    from the in-memory version, so every caller (GroundedQAService,
    ComparisonService, chat_across_papers, the API endpoints) needed no changes.
    """

    def __init__(self, db: WorkspaceManager) -> None:
        self._db = db
        self._histories: Dict[str, List[ChatMessage]] = {}
        self._lock = threading.Lock()

    def get(self, workspace_id: UUID) -> List[ChatMessage]:
        key = str(workspace_id)
        with self._lock:
            if key in self._histories:
                return list(self._histories[key])

        rows = self._db.get_chat_messages(workspace_id)
        history = [ChatMessage(role=row["role"], content=row["content"]) for row in rows]
        with self._lock:
            self._histories[key] = history
            return list(history)

    def set(self, workspace_id: UUID, history: List[ChatMessage]) -> None:
        max_messages = get_settings().memory_max_messages
        trimmed = list(history[-max_messages:]) if max_messages > 0 else list(history)

        with self._lock:
            self._histories[str(workspace_id)] = trimmed
        self._db.replace_chat_messages(
            workspace_id,
            # ChatMessage.role is a MessageRole enum; str(m.role) would store
            # "MessageRole.USER" rather than "user" and fail to round-trip
            # through ChatMessage(role=...) on the next get(). .value is the
            # plain "user"/"assistant" string the constructor expects back.
            [(m.role.value, str(m.content)) for m in trimmed],
        )

    def clear(self, workspace_id: UUID) -> None:
        with self._lock:
            self._histories.pop(str(workspace_id), None)
        self._db.clear_chat_messages(workspace_id)


@lru_cache(maxsize=1)
def get_db_manager() -> WorkspaceManager:
    settings = get_settings()
    settings.ensure_directories()
    db_path = settings.db_path
    return WorkspaceManager(db_path=db_path)

@lru_cache(maxsize=1)
def get_embedding_engine() -> EmbeddingEngine:
    return EmbeddingEngine()

@lru_cache(maxsize=1)
def get_paper_session_manager() -> PaperSessionManager:
    return PaperSessionManager()

@lru_cache(maxsize=1)
def get_workspace_chat_store() -> WorkspaceChatStore:
    return WorkspaceChatStore(db=get_db_manager())

@lru_cache(maxsize=1)
def get_search_agent() -> SearchAgent:
    """Cached SearchAgent so providers/ranker/embedding model are built once.

    Previously each /api/search request rebuilt the SearchAgent, PaperRanker,
    and both providers from scratch, forcing a fresh httpx client and (on the
    first call) a synchronous embedding-model load per request.
    """
    settings = get_settings()
    ranker = PaperRanker(engine=get_embedding_engine())
    providers = [
        ArxivProvider(),
        SemanticScholarProvider(api_key=settings.semantic_scholar_api_key),
    ]
    return SearchAgent(providers=providers, ranker=ranker)

@lru_cache(maxsize=1)
def get_tutor_agent() -> TutorAgent:
    """Build a TutorAgent on whichever LLM provider is configured and reachable.

    Provider selection (and its fallback order) is owned by paperpilot.llm so
    the agents and the LlamaIndex RAG engine can't drift onto different
    backends. Raises LLMConfigurationError if nothing can be built.

    Cached because the agent is stateless (all conversation state is passed in
    per call) and constructing the chat model re-reads settings and re-imports
    the provider SDK.
    """
    return TutorAgent(chat_model=build_chat_model())


@lru_cache(maxsize=1)
def get_critic_agent() -> CriticAgent:
    """CriticAgent sharing the same provider resolution as the tutor."""
    return CriticAgent(chat_model=build_chat_model())


def get_optional_grounded_qa_service() -> GroundedQAService | None:
    """The grounded-QA service, or None if it is disabled or unavailable.

    Returning None rather than raising lets the chat endpoint fall back to the
    plain LlamaIndex path: if the agents' chat model can't be built (no key, SDK
    missing), degraded chat beats a 500 on every question. It is also the seam
    tests override to inject a stub service.
    """
    if not get_settings().rag_grounded_qa_enabled:
        return None
    try:
        return get_grounded_qa_service()
    except LLMConfigurationError as e:
        logger.error("Grounded QA unavailable, falling back to default chat: %s", e)
        return None


@lru_cache(maxsize=1)
def get_summarizer_service() -> SummarizerService:
    """Multi-level summarizer sharing the grounded-QA path (and its critic)."""
    return SummarizerService(qa_service=get_grounded_qa_service())


@lru_cache(maxsize=1)
def get_grounded_qa_service() -> GroundedQAService:
    """The production grounded-QA path: retrieve -> tutor -> critic -> retry.

    Safe to cache: the service holds only its injected collaborators, and every
    per-conversation value (history, question, difficulty) is a call argument.
    """
    settings = get_settings()
    return GroundedQAService(
        session_manager=get_paper_session_manager(),
        tutor=get_tutor_agent(),
        critic=get_critic_agent(),
        max_retries=settings.rag_max_critique_retries,
        critique_enabled=settings.rag_critique_enabled,
    )


@lru_cache(maxsize=1)
def get_comparison_agent() -> ComparisonAgent:
    """ComparisonAgent sharing the same provider resolution as tutor/critic."""
    return ComparisonAgent(chat_model=build_chat_model())


@lru_cache(maxsize=1)
def get_comparison_service() -> ComparisonService:
    """The production comparison path: retrieve per paper -> agent -> critic -> retry."""
    settings = get_settings()
    return ComparisonService(
        session_manager=get_paper_session_manager(),
        comparison_agent=get_comparison_agent(),
        critic=get_critic_agent(),
        max_retries=settings.rag_max_critique_retries,
        critique_enabled=settings.rag_critique_enabled,
    )


def get_optional_comparison_service() -> ComparisonService | None:
    """The comparison service, or None if the agents' LLM can't be built.

    Mirrors get_optional_grounded_qa_service: a missing/broken provider key
    degrades the /compare endpoint to a clear error instead of a 500, and is
    the seam tests override to inject a stub service.
    """
    try:
        return get_comparison_service()
    except LLMConfigurationError as e:
        logger.error("Comparison unavailable: %s", e)
        return None
