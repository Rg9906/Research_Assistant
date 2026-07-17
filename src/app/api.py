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

@app.post("/api/workspaces/{workspace_id}/chat", response_model=ChatResponse)
def chat_with_workspace(workspace_id: UUID, message: ChatMessage):
    # Retrieve pipeline initialized for this workspace
    pipeline = get_document_pipeline(workspace_id)
    
    # Ensure there are papers to chat with
    papers = pipeline.db_manager.get_workspace_papers(workspace_id)
    if not papers:
        raise HTTPException(status_code=400, detail="Workspace is empty. Add papers first.")

    try:
        # We need to answer the question using the vector store
        # The pipeline assumes papers have been loaded into the FAISS store
        # For simplicity, if not loaded, we should ideally load them.
        # But `pipeline.answer_question` expects chunks to be retrieved.
        # This implementation requires chunks to be already in the FAISS store.
        answer = pipeline.answer_question(message.query)
        return ChatResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
