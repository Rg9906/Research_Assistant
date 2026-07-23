"""
Paper ranker using multi-factor weighted scoring.

This module implements PaperRanker, which scores and sorts candidate papers
based on:
1. Semantic Similarity: Query vector vs. Paper title + abstract vector.
2. Citation Count: Normalized log-scaling.
3. Recency: Exponential time decay.
4. PDF Availability: How likely the paper can actually be opened and chatted
   with (see search/availability.py). A paper we cannot download is a dead end
   in this product, so availability is a first-class ranking dimension rather
   than a post-hoc filter.
"""

from __future__ import annotations

import datetime
import logging
import numpy as np

from paperpilot.config import get_settings
from paperpilot.core.models import PaperMetadata
from paperpilot.retrieval.embedder import EmbeddingEngine
from paperpilot.search.availability import pdf_availability_score

logger = logging.getLogger(__name__)


class PaperRanker:
    """Calculates weighted ranking scores for search candidate papers.

    Assigns scores based on semantic similarity, citation counts, and publication recency.
    Decoupled from search APIs and embedding model details.

    Formula:
        Score = w_sim * S_sim + w_cit * S_cit + w_rec * S_rec + w_avail * S_avail
    """

    def __init__(
        self,
        engine: EmbeddingEngine,
        weight_similarity: float | None = None,
        weight_citations: float | None = None,
        weight_recency: float | None = None,
        weight_availability: float | None = None,
        decay_rate: float | None = None,
    ) -> None:
        """Initialize the Paper Ranker.

        Args:
            engine: Injected EmbeddingEngine instance.
            weight_similarity: Weight for semantic matching.
            weight_citations: Weight for citation counts.
            weight_recency: Weight for age decay.
            weight_availability: Weight for PDF availability (chattability).
            decay_rate: Constant governing publication age decay.
        """
        self.engine = engine

        settings = get_settings()
        self.w_sim = weight_similarity if weight_similarity is not None else settings.search_weight_similarity
        self.w_cit = weight_citations if weight_citations is not None else settings.search_weight_citations
        self.w_rec = weight_recency if weight_recency is not None else settings.search_weight_recency
        self.w_avail = weight_availability if weight_availability is not None else settings.search_weight_availability
        self.decay_rate = decay_rate if decay_rate is not None else settings.search_decay_rate

        # Enforce weights sum to 1.0 (approximate check to allow float precision)
        total_weight = self.w_sim + self.w_cit + self.w_rec + self.w_avail
        if not np.isclose(total_weight, 1.0):
            logger.warning(
                "Ranking weights do not sum to 1.0 (got %0.2f). Normalizing them.",
                total_weight,
            )
            self.w_sim /= total_weight
            self.w_cit /= total_weight
            self.w_rec /= total_weight
            self.w_avail /= total_weight

        logger.info(
            "PaperRanker initialized (w_sim=%0.2f, w_cit=%0.2f, w_rec=%0.2f, w_avail=%0.2f, decay_rate=%0.3f)",
            self.w_sim,
            self.w_cit,
            self.w_rec,
            self.w_avail,
            self.decay_rate,
        )

    def rank_papers(
        self,
        query: str,
        papers: list[PaperMetadata],
    ) -> list[tuple[PaperMetadata, float]]:
        """Rank a list of papers based on query relevance and metadata.

        Args:
            query: User search topic.
            papers: Candidate list of papers.

        Returns:
            List of (PaperMetadata, total_score) sorted by score descending.
        """
        if not papers:
            return []

        logger.info("Ranking %d candidate papers for query: '%s'", len(papers), query)

        # Step 1: Calculate Semantic Similarity Scores
        # Combine title and abstract for a richer semantic representation.
        # Fallback to title if abstract is not available.
        paper_texts = []
        for paper in papers:
            text = paper.title
            if paper.abstract:
                text += f" {paper.abstract}"
            paper_texts.append(text)

        # Embed query and papers
        query_vector = self.engine.embed_query(query)
        paper_vectors = self.engine.embed_texts(paper_texts)

        # Since embeddings are L2-normalized, cosine similarity is the dot product.
        # dot product yields 1D array of similarity scores for each paper.
        sim_scores = np.dot(paper_vectors, query_vector)
        # Clip negative values to 0.0 (semantic similarity shouldn't be negative for RAG)
        sim_scores = np.clip(sim_scores, 0.0, 1.0)

        # Step 2: Calculate Citation Impact Scores
        # citation counts follow power-law, we use log-scaling
        cit_counts = [p.citation_count if p.citation_count is not None else 0 for p in papers]
        max_citations = max(cit_counts)
        
        cit_scores = []
        for cit in cit_counts:
            # S_cit = log(1 + citation_count) / log(1 + max_citations)
            if max_citations > 0:
                score = np.log1p(cit) / np.log1p(max_citations)
            else:
                score = 0.0
            cit_scores.append(score)

        # Step 3: Calculate Recency Scores
        current_year = datetime.datetime.now().year
        rec_scores = []
        for paper in papers:
            if paper.publication_year is not None:
                age = max(0, current_year - paper.publication_year)
                # Exponential decay: e^(-lambda * age)
                score = np.exp(-self.decay_rate * age)
            else:
                # If publication year is unknown, assign a fallback score
                score = 0.5
            rec_scores.append(score)

        # Step 4: Calculate PDF availability scores.
        # A paper we cannot download is unchattable and unsummarizable — the
        # whole product past discovery is gated on the PDF. Availability is
        # graded (open repository > direct .pdf > landing page > none) rather
        # than boolean, so a guaranteed-openable arXiv paper outranks an S2 hit
        # whose openAccessPdf is a publisher landing page. See availability.py.
        avail_scores = [pdf_availability_score(p) for p in papers]

        # Step 5: Calculate final weighted score
        ranked_list: list[tuple[PaperMetadata, float]] = []
        for i, paper in enumerate(papers):
            total_score = (
                self.w_sim * sim_scores[i]
                + self.w_cit * cit_scores[i]
                + self.w_rec * rec_scores[i]
                + self.w_avail * avail_scores[i]
            )
            ranked_list.append((paper, float(total_score)))

            logger.debug(
                "Paper '%s': total=%0.4f (sim=%0.4f, cit=%0.4f, rec=%0.4f, avail=%0.4f)",
                paper.title[:30],
                total_score,
                sim_scores[i],
                cit_scores[i],
                rec_scores[i],
                avail_scores[i],
            )

        # Sort descending by total score
        ranked_list.sort(key=lambda x: x[1], reverse=True)

        logger.info("Ranking complete. Top paper: '%s' (score=%0.4f)", ranked_list[0][0].title[:50], ranked_list[0][1])
        return ranked_list
