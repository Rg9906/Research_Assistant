from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any
from uuid import UUID

from app.utils import get_db_manager, get_document_pipeline
from paperpilot.core.models import PaperMetadata
from paperpilot.workspace.manager import WorkspaceManager
from paperpilot.pipeline import DocumentPipeline
from paperpilot.search.agent import SearchAgent
from paperpilot.search.ranker import PaperRanker
from app.utils import get_embedding_engine

app = FastAPI(title="PaperPilot AI API")

# Enable CORS for the Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the Vite dev server URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
def delete_workspace(workspace_id: UUID, db: WorkspaceManager = Depends(get_db_manager)):
    db.delete_workspace(workspace_id)
    return {"status": "success"}

@app.get("/api/workspaces/{workspace_id}/papers", response_model=List[Any])
def list_workspace_papers(workspace_id: UUID, db: WorkspaceManager = Depends(get_db_manager)):
    papers = db.get_workspace_papers(workspace_id)
    # Convert PaperMetadata to dict for response
    return [p.model_dump() for p in papers]

@app.post("/api/search")
def search_papers(query: SearchQuery, engine = Depends(get_embedding_engine)):
    from paperpilot.search.providers import ArxivProvider, SemanticScholarProvider
    ranker = PaperRanker(engine=engine)
    providers = [ArxivProvider(), SemanticScholarProvider()]
    agent = SearchAgent(providers=providers, ranker=ranker)
    try:
        # discover_papers returns a list of tuples (PaperMetadata, score)
        results = agent.discover_papers(query.query, top_n=query.limit)
        return {"results": [p[0].model_dump() for p in results]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

from app.utils import get_paper_session_manager
from paperpilot.services.paper_chat import PaperSessionManager

@app.post("/api/workspaces/{workspace_id}/chat", response_model=ChatResponse)
def chat_with_workspace(
    workspace_id: UUID,
    message: ChatMessage,
    db: WorkspaceManager = Depends(get_db_manager),
    session_manager: PaperSessionManager = Depends(get_paper_session_manager),
):
    papers = db.get_workspace_papers(workspace_id)
    if not papers:
        raise HTTPException(status_code=400, detail="Workspace is empty. Add papers first.")

    paper = papers[0]
    try:
        session = session_manager.get_or_create_session(metadata=paper, pdf_url=paper.pdf_url)
        answer = session.chat(message.query)
        return ChatResponse(answer=answer)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/papers/process")
def process_paper(
    request: ProcessPaperRequest,
    db: WorkspaceManager = Depends(get_db_manager),
    session_manager: PaperSessionManager = Depends(get_paper_session_manager),
):
    if not request.pdf_url:
        raise HTTPException(status_code=400, detail="Cannot process paper without a PDF URL")
    
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
            raise HTTPException(status_code=500, detail="Failed to create or find workspace")

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
    
    db.add_paper_to_workspace(workspace_id, paper_meta, chunks=[])
    
    try:
        session_manager.get_or_create_session(metadata=paper_meta, pdf_url=request.pdf_url)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process PDF with LlamaIndex: {e}")
        
    return {"workspace_id": str(workspace_id)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
