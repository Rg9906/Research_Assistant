"""
Integration tests for the full RAG pipeline (Retrieval + LLM Generation).

These tests run the entire DocumentPipeline with a TutorAgent using a real
ChatModel. If OPENAI_API_KEY is not configured in the environment or .env,
these tests are skipped.
"""

import os
from pathlib import Path

import fitz
import pytest
from langchain_openai import ChatOpenAI

from paperpilot.config import get_settings
from paperpilot.core.models import PaperMetadata
from paperpilot.pipeline import DocumentPipeline
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.retrieval.vector_store import FAISSVectorStore
from paperpilot.agent.tutor import TutorAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_key() -> str:
    """Retrieve OpenAI API key, reading from settings/env."""
    settings = get_settings()
    # Read from settings (which checks .env) or direct env fallback
    key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
    return key


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory) -> Path:
    """Create a synthetic PDF with specific facts for testing."""
    tmp_path = tmp_path_factory.mktemp("rag_data")
    pdf_path = tmp_path / "rag_paper.pdf"
    
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    text = (
        "Testora: Using Natural Language Intent\n\n"
        "Testora is an automated technique to detect regressions by comparing "
        "the intentions of a code change against behavioral differences. "
        "It uses a multi-question LLM-based classifier to determine if a "
        "behavioral difference exposed by a test is intended. "
        "The evaluation was performed on four projects: keras, marshmallow, "
        "pandas, and scipy. Testora found 19 regressions in total.\n\n"
        "The costs of Testora are very low, averaging only $0.003 in LLM tokens "
        "per analyzed pull request."
    )
    page.insert_text(fitz.Point(50, 50), text, fontsize=11)
    doc.save(str(pdf_path))
    doc.close()
    
    return pdf_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPipelineRAG:
    """Integration tests executing real RAG queries."""

    def test_rag_pipeline_flow(self, api_key: str, sample_pdf: Path):
        """Test RAG flow: processes paper, answers grounded query, and refuses ungrounded query."""
        if not api_key:
            pytest.skip("OPENAI_API_KEY is not configured. Skipping RAG integration tests.")

        settings = get_settings()
        
        # 1. Setup pipeline with real ChatModel
        engine = EmbeddingEngine(model_name="all-MiniLM-L6-v2")
        store = FAISSVectorStore(dimension=engine.embedding_dim)
        
        chat_model = ChatOpenAI(
            openai_api_key=api_key,
            model=settings.llm_model_name,
            temperature=settings.llm_temperature,
        )
        tutor = TutorAgent(chat_model=chat_model)
        
        pipeline = DocumentPipeline(engine, store, tutor)

        # 2. Process document
        metadata = PaperMetadata(title="Testora Integration Test")
        pipeline.process_pdf(sample_pdf, metadata=metadata, chunk_size=500, chunk_overlap=50)

        import openai
        try:
            # 3. Ask grounded query (should answer using details from context)
            query = "How many regressions did Testora find in the projects?"
            answer = pipeline.answer_question(query)

            assert "19" in answer
            assert "regressions" in answer.lower()

            # 4. Ask ungrounded/irrelevant query (should trigger strict grounding refusal)
            ungrounded_query = "What is the capital city of France?"
            refusal_answer = pipeline.answer_question(ungrounded_query)

            assert refusal_answer == "I cannot find the answer in the provided text."
        except openai.RateLimitError as e:
            pytest.skip(f"OpenAI RateLimit/Quota exceeded: {e}")
        except openai.AuthenticationError as e:
            pytest.skip(f"OpenAI API Key authentication failed: {e}")
        except Exception as e:
            # If it's a generic API error containing quota/auth info, skip it
            e_str = str(e).lower()
            if "quota" in e_str or "rate limit" in e_str or "auth" in e_str:
                pytest.skip(f"OpenAI API issue: {e}")
            raise e
