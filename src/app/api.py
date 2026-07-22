import sys
from pathlib import Path

# `app` is a namespace package, not an installed one (see CLAUDE.md §2), so
# `from app.utils import ...` below only resolves if src/ is on sys.path. Adding
# it here lets the server be started from the repo root as well as from src/.
sys.path.append(str(Path(__file__).resolve().parent.parent))

import logging
from contextlib import asynccontextmanager

# Must run before anything opens a TLS connection (model downloads, provider
# SDKs), so it sits above those imports deliberately. See paperpilot/net.py.
from paperpilot.net import enable_hf_offline_if_cached, enable_system_trust_store

enable_system_trust_store()

# If both embedding models are already cached, skip Hugging Face's per-startup
# update check (which can add minutes when huggingface.co is unreachable). Done
# here, before the embedding libraries are imported, so HF_HUB_OFFLINE is set in
# time to take effect. Falls through to online mode on a first run.
from paperpilot.config import get_settings as _get_settings

_s = _get_settings()
enable_hf_offline_if_cached(
    [_s.rag_embedding_model, _s.embedding_model_name]
    + ([_s.rag_rerank_model] if _s.rag_rerank_enabled else [])
)

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any
from uuid import UUID

from app.utils import (
    get_db_manager,
    get_search_agent,
    get_paper_session_manager,
    get_workspace_chat_store,
    get_embedding_engine,
    get_optional_grounded_qa_service,
    get_summarizer_service,
    WorkspaceChatStore,
)
from paperpilot.services.grounded_qa import GroundedQAService
from paperpilot.services.summarizer import SUMMARY_LEVELS, SummarizerService
from paperpilot.core.models import PaperMetadata
from paperpilot.workspace.manager import WorkspaceManager
from paperpilot.search.agent import SearchAgent
from paperpilot.services.paper_chat import PaperSessionManager
from paperpilot.services.paper_chat.exceptions import PaperChatException

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the embedding model and session manager before serving traffic.

    Both singletons load (and on a cold machine, download) Hugging Face models
    on first use. Doing that lazily inside the first /api/search or
    /api/papers/process request makes that request appear to hang for minutes,
    so pay the cost at startup instead. Warm-up failures are logged, not
    raised: a server that starts degraded is more useful than one that refuses
    to boot, and the real error surfaces on the request that needs the model.
    """
    for label, factory in (
        ("search embedding engine", get_embedding_engine),
        ("paper session manager", get_paper_session_manager),
    ):
        logger.info("Warming up %s...", label)
        try:
            factory()
            logger.info("%s ready.", label.capitalize())
        except Exception:
            logger.exception("Failed to warm up %s", label)
    yield


app = FastAPI(title="PaperPilot AI API", lifespan=lifespan)

# CORS: the frontend calls this API with plain `fetch` (no cookies/auth
# headers), so we don't need `allow_credentials=True`. Combining a wildcard
# origin with credentials is invalid per the CORS spec and browsers will
# reject it anyway; keep the wildcard for local-dev convenience across
# whatever port Vite picks, but leave credentials off.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _fail(status_code: int, log_message: str, error: Exception) -> HTTPException:
    """Log full exception details server-side, return a sanitized client error.

    Raw exception text (`str(e)`) can leak internal paths, stack details, or
    provider error payloads to the client. Callers should log the message +
    exception via `logger.exception` before raising this.
    """
    logger.exception(log_message)
    return HTTPException(status_code=status_code, detail=log_message)


# Models
class WorkspaceCreate(BaseModel):
    name: str

class WorkspaceResponse(BaseModel):
    workspace_id: UUID
    name: str
    paper_count: int

class SearchQuery(BaseModel):
    query: str
    limit: int = 5

class ChatMessage(BaseModel):
    query: str
    # Explanation level, forwarded to both the tutor and the critic (which
    # audits whether the answer actually matched the level asked for).
    difficulty: str = "graduate/expert"

class Citation(BaseModel):
    rank: int
    # None for a lead chunk (the paper's intro, always included as context and
    # not scored by similarity). The UI labels these instead of showing 0.00.
    score: Optional[float] = None
    is_lead: bool = False
    text: str
    page_number: str
    paper_id: Optional[str] = None
    filename: str

class ChatResponse(BaseModel):
    answer: str
    # Citations and the audit verdict are part of the response contract, not
    # debug extras: the product promise is answers traceable to the source, so
    # the UI needs the evidence and the flag for "this failed review".
    citations: List[Citation] = []
    approved: bool = True
    refused: bool = False
    attempts: int = 1
    critique: Optional[str] = None

class SummaryResponse(BaseModel):
    paper_id: UUID
    level_id: str
    summary: str
    # Surfaced so the UI can distinguish "instant" from "just cost an LLM call"
    # and offer regeneration only where it means something.
    from_cache: bool

class ProcessPaperRequest(BaseModel):
    paper_id: UUID
    title: str
    authors: List[str]
    publication_year: Optional[int] = None
    citation_count: Optional[int] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    pdf_url: Optional[str] = None
    venue: Optional[str] = None

# Endpoints
@app.get("/api/workspaces", response_model=List[WorkspaceResponse])
def list_workspaces(db: WorkspaceManager = Depends(get_db_manager)):
    workspaces = db.list_workspaces()
    return [
        WorkspaceResponse(
            workspace_id=w["workspace_id"],
            name=w["name"],
            paper_count=w["paper_count"]
        ) for w in workspaces
    ]

@app.post("/api/workspaces", response_model=WorkspaceResponse)
def create_workspace(workspace: WorkspaceCreate, db: WorkspaceManager = Depends(get_db_manager)):
    try:
        workspace_id = db.create_workspace(workspace.name)
        return WorkspaceResponse(workspace_id=workspace_id, name=workspace.name, paper_count=0)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: UUID,
    db: WorkspaceManager = Depends(get_db_manager),
    chat_store: WorkspaceChatStore = Depends(get_workspace_chat_store),
):
    db.delete_workspace(workspace_id)
    chat_store.set(workspace_id, [])
    return {"status": "success"}

@app.get("/api/workspaces/{workspace_id}/papers", response_model=List[Any])
def list_workspace_papers(workspace_id: UUID, db: WorkspaceManager = Depends(get_db_manager)):
    papers = db.get_workspace_papers(workspace_id)
    # Convert PaperMetadata to dict for response
    return [p.model_dump() for p in papers]

@app.post("/api/search")
def search_papers(query: SearchQuery, agent: SearchAgent = Depends(get_search_agent)):
    try:
        # discover_papers returns a list of tuples (PaperMetadata, score)
        results = agent.discover_papers(query.query, top_n=query.limit)
        return {"results": [p[0].model_dump() for p in results]}
    except Exception as e:
        raise _fail(500, f"Search failed for query '{query.query}'", e)

@app.post("/api/workspaces/{workspace_id}/chat", response_model=ChatResponse)
def chat_with_workspace(
    workspace_id: UUID,
    message: ChatMessage,
    db: WorkspaceManager = Depends(get_db_manager),
    session_manager: PaperSessionManager = Depends(get_paper_session_manager),
    chat_store: WorkspaceChatStore = Depends(get_workspace_chat_store),
    qa_service: Optional[GroundedQAService] = Depends(get_optional_grounded_qa_service),
):
    papers = db.get_workspace_papers(workspace_id)
    if not papers:
        raise HTTPException(status_code=400, detail="Workspace is empty. Add papers first.")

    titles = ", ".join(p.title for p in papers)
    try:
        # Both paths fan the query out across every paper's index rather than
        # answering from the first paper only. The underlying PaperSession/index
        # is shared across every workspace referencing a paper, but conversation
        # memory must not be — it is scoped by workspace_id so unrelated
        # workspaces don't see each other's history.
        history = chat_store.get(workspace_id)

        if qa_service is not None:
            # Retrieval -> TutorAgent (answer strictly from chunks, else refuse)
            # -> CriticAgent audit -> bounded retry. See services/grounded_qa.py.
            result = qa_service.answer(
                papers, message.query, chat_history=history, difficulty=message.difficulty
            )
            chat_store.set(workspace_id, result.chat_history)
            return ChatResponse(
                answer=result.answer,
                citations=[Citation(**{k: c[k] for k in Citation.model_fields}) for c in result.citations],
                approved=result.approved,
                refused=result.refused,
                attempts=result.attempts,
                critique=result.critique.feedback if result.critique else None,
            )

        answer, sources, updated_history = session_manager.chat_across_papers(
            papers, message.query, chat_history=history
        )
        chat_store.set(workspace_id, updated_history)
        return ChatResponse(
            answer=answer,
            citations=[Citation(**{k: c[k] for k in Citation.model_fields}) for c in sources],
        )
    except PaperChatException as e:
        raise _fail(502, f"Chat failed for workspace papers [{titles}]: {e}", e)
    except Exception as e:
        raise _fail(500, f"Unexpected error during chat for workspace papers [{titles}]", e)

@app.get("/api/summary-levels")
def list_summary_levels():
    """The catalogue of summary views, defined server-side.

    The frontend renders whatever this returns instead of hardcoding its own
    prompts, so adding a level is a backend-only change.
    """
    return {
        "levels": [
            {"id": level.id, "label": level.label, "difficulty": level.difficulty}
            for level in SUMMARY_LEVELS
        ]
    }


@app.post("/api/papers/{paper_id}/summary/{level_id}", response_model=SummaryResponse)
def summarize_paper(
    paper_id: UUID,
    level_id: str,
    regenerate: bool = False,
    db: WorkspaceManager = Depends(get_db_manager),
    summarizer: SummarizerService = Depends(get_summarizer_service),
):
    """Generate (or serve from cache) one summary level for an indexed paper."""
    paper = db.get_paper_by_id(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found. Process it first.")

    try:
        summary, from_cache = summarizer.summarize(paper, level_id, regenerate=regenerate)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown summary level '{level_id}'")
    except PaperChatException as e:
        raise _fail(502, f"Failed to summarize '{paper.title}' at level '{level_id}': {e}", e)
    except Exception as e:
        raise _fail(500, f"Unexpected error summarizing '{paper.title}'", e)

    return SummaryResponse(
        paper_id=paper_id, level_id=level_id, summary=summary, from_cache=from_cache
    )


@app.post("/api/papers/process")
def process_paper(
    request: ProcessPaperRequest,
    db: WorkspaceManager = Depends(get_db_manager),
    session_manager: PaperSessionManager = Depends(get_paper_session_manager),
):
    if not request.pdf_url:
        raise HTTPException(status_code=400, detail="Cannot process paper without a PDF URL")

    paper_meta = PaperMetadata(
        paper_id=request.paper_id,
        title=request.title,
        authors=request.authors,
        publication_year=request.publication_year,
        citation_count=request.citation_count,
        abstract=request.abstract,
        doi=request.doi,
        pdf_url=request.pdf_url,
        venue=request.venue
    )

    # Build/download the index BEFORE writing anything to the workspace DB.
    # Previously the paper was persisted first and indexed second, so a
    # download/parse/embedding failure left a permanently unchattable paper
    # sitting in the workspace with no way to retry via the UI.
    try:
        session_manager.get_or_create_session(metadata=paper_meta, pdf_url=request.pdf_url)
    except PaperChatException as e:
        raise _fail(502, f"Failed to process PDF for '{request.title}': {e}", e)
    except Exception as e:
        raise _fail(500, f"Unexpected error indexing '{request.title}'", e)

    workspace_name = f"Paper: {request.title}"[:50]
    try:
        workspace_id = db.create_workspace(workspace_name)
    except ValueError:
        workspaces = db.list_workspaces()
        for w in workspaces:
            if w["name"] == workspace_name:
                workspace_id = w["workspace_id"]
                break
        else:
            raise _fail(500, "Failed to create or find workspace", ValueError(workspace_name))

    db.add_paper_to_workspace(workspace_id, paper_meta, chunks=[])

    return {"workspace_id": str(workspace_id)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
