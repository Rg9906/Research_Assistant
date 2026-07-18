import os
import logging
import threading
from functools import lru_cache
from typing import Dict, List
from uuid import UUID

from langchain_openai import ChatOpenAI
from llama_index.core.llms import ChatMessage
from paperpilot.config import get_settings
from paperpilot.workspace.manager import WorkspaceManager
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.agent.tutor import TutorAgent
from paperpilot.search.agent import SearchAgent
from paperpilot.search.ranker import PaperRanker
from paperpilot.search.providers import ArxivProvider, SemanticScholarProvider
from paperpilot.services.paper_chat import PaperSessionManager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class WorkspaceChatStore:
    """Process-local store of per-workspace chat memory.

    PaperSession no longer holds conversation state itself (a single cached
    session is shared by every workspace/user asking about the same paper —
    see paperpilot.services.paper_chat.session._build_chat_engine), so
    something above it must own "which messages belong to this
    conversation." A workspace is the unit of conversation the API exposes
    (`/api/workspaces/{id}/chat`), so history is scoped by workspace_id here.

    This is an in-memory dict, matching the rest of the app's process-local
    caching (WorkspaceManager connections, PaperSessionManager sessions) —
    history does not survive a server restart. Persisting it to the
    workspace DB is future work if cross-restart memory is needed.
    """

    def __init__(self) -> None:
        self._histories: Dict[str, List[ChatMessage]] = {}
        self._lock = threading.Lock()

    def get(self, workspace_id: UUID) -> List[ChatMessage]:
        with self._lock:
            return list(self._histories.get(str(workspace_id), []))

    def set(self, workspace_id: UUID, history: List[ChatMessage]) -> None:
        with self._lock:
            self._histories[str(workspace_id)] = history


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
    return WorkspaceChatStore()

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

def get_tutor_agent() -> TutorAgent:
    settings = get_settings()
    api_key = os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
    if not api_key:
        print("WARNING: OPENAI_API_KEY is not set. Tutor Agent will not work.")
    
    # Initialize ChatOpenAI with configured parameters for strict grounding
    chat_model = ChatOpenAI(
        model=settings.llm_model_name,
        temperature=settings.llm_temperature,
        openai_api_key=api_key
    )
    return TutorAgent(chat_model=chat_model)
