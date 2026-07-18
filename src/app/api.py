import logging
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
    WorkspaceChatStore,
)
from paperpilot.core.models import PaperMetadata
from paperpilot.workspace.manager import WorkspaceManager
from paperpilot.search.agent import SearchAgent
from paperpilot.services.paper_chat import PaperSessionManager
from paperpilot.services.paper_chat.exceptions import PaperChatException

logger = logging.getLogger(__name__)

app = FastAPI(title="PaperPilot AI API")

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

class ChatResponse(BaseModel):
    answer: str

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
):
    papers = db.get_workspace_papers(workspace_id)
    if not papers:
        raise HTTPException(status_code=400, detail="Workspace is empty. Add papers first.")

    titles = ", ".join(p.title for p in papers)
    try:
        # Fans the query out across every paper's index and merges results by
        # score (see PaperSessionManager.chat_across_papers), so a workspace
        # with several papers is grounded in all of them, not just the first.
        # The underlying PaperSession/index is shared across every workspace
        # that references a given paper, but conversation memory must not be
        # — scope it by workspace_id so unrelated workspaces don't see each
        # other's chat history.
        history = chat_store.get(workspace_id)
        answer, _sources, updated_history = session_manager.chat_across_papers(
            papers, message.query, chat_history=history
        )
        chat_store.set(workspace_id, updated_history)
        return ChatResponse(answer=answer)
    except PaperChatException as e:
        raise _fail(502, f"Chat failed for workspace papers [{titles}]: {e}", e)
    except Exception as e:
        raise _fail(500, f"Unexpected error during chat for workspace papers [{titles}]", e)

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
