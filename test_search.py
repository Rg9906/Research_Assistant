"""Manual live-network verification script for the Search Agent.

Not part of the pytest suite (pyproject.toml scopes testpaths to `tests/`,
which mocks all external calls). Run directly with `python test_search.py`
to sanity-check real arXiv/Semantic Scholar responses and ranking end-to-end.
"""

import logging
from paperpilot.config import get_settings
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.search.providers import ArxivProvider, SemanticScholarProvider
from paperpilot.search.ranker import PaperRanker
from paperpilot.search.agent import SearchAgent

# Configure logging to see steps
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

def test_live_search():
    settings = get_settings()

    # 1. Initialize embedding engine (for title/abstract semantic matching)
    print("Loading embedding engine...")
    engine = EmbeddingEngine(model_name=settings.embedding_model_name)

    # 2. Setup providers (using arXiv only or both)
    # Semantic Scholar is rate-limited without a key, so we handle it gracefully.
    arxiv_prov = ArxivProvider()
    sem_prov = SemanticScholarProvider(api_key=settings.semantic_scholar_api_key)
    
    # 3. Setup ranker
    ranker = PaperRanker(engine=engine)

    # 4. Setup agent
    agent = SearchAgent(providers=[arxiv_prov, sem_prov], ranker=ranker)

    # 5. Run live search discovery
    query = "attention is all you need transformer"
    print(f"\n--- Searching for: '{query}' ---")
    
    results = agent.discover_papers(query, limit_per_provider=5, top_n=5)

    print("\n--- Final Ranked Search Results ---")
    for i, (paper, score) in enumerate(results, start=1):
        print(f"\n[{i}] Score: {score:.4f}")
        print(f"Title: {paper.title}")
        print(f"Authors: {', '.join(paper.authors[:3])}...")
        print(f"Year: {paper.publication_year} | Venue: {paper.venue}")
        print(f"Citations: {paper.citation_count}")
        print(f"DOI: {paper.doi}")
        print(f"PDF Link: {paper.pdf_url}")
        print(f"Abstract: {paper.abstract[:150] if paper.abstract else 'No abstract'}...")
        print("-" * 50)

if __name__ == "__main__":
    test_live_search()
