import os
from functools import lru_cache
from pathlib import Path
from langchain_openai import ChatOpenAI
from paperpilot.config import get_settings
from paperpilot.workspace.manager import WorkspaceManager
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.retrieval.vector_store import FAISSVectorStore
from paperpilot.agent.tutor import TutorAgent
from paperpilot.pipeline import DocumentPipeline
from dotenv import load_dotenv

load_dotenv()

@lru_cache(maxsize=1)
def get_db_manager() -> WorkspaceManager:
    settings = get_settings()
    settings.ensure_directories()
    db_path = settings.db_path
    return WorkspaceManager(db_path=db_path)

@lru_cache(maxsize=1)
def get_embedding_engine() -> EmbeddingEngine:
    return EmbeddingEngine()

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

def get_document_pipeline(workspace_id=None) -> DocumentPipeline:
    engine = get_embedding_engine()
    store = FAISSVectorStore(dimension=engine.embedding_dim)
    tutor = get_tutor_agent()
    db_manager = get_db_manager()
    
    return DocumentPipeline(
        engine=engine,
        store=store,
        tutor=tutor,
        db_manager=db_manager,
        workspace_id=workspace_id
    )
