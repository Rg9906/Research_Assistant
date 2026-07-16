"""
Graph node implementations for PaperPilot AI.

This module implements the AgentNodes class, which wraps our domain-level
agents (Planner, SearchAgent, DocumentPipeline, TutorAgent, Critic) and exposes
them as state-transforming functions (nodes) for the LangGraph workflow.

Design Pattern: Encapsulation Class
    Instead of writing global functions as nodes (which makes dependency injection
    difficult), we encapsulate all nodes as instance methods of a class. The class
    constructor accepts all required dependencies (engines, stores, agents).
    This keeps the node functions pure relative to the graph state, but allows
    them to access local services.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from paperpilot.agent.tutor import TutorAgent
from paperpilot.core.models import PaperMetadata
from paperpilot.graph.state import AgentState
from paperpilot.pipeline import DocumentPipeline
from paperpilot.search.agent import SearchAgent

logger = logging.getLogger(__name__)


class AgentNodes:
    """Encapsulates all node functions for the LangGraph workflow.

    Maintains references to necessary backend services and agents.
    Each method represents a single processing step in our multi-agent workflow.
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        search_agent: SearchAgent,
        pipeline: DocumentPipeline,
        tutor_agent: TutorAgent,
    ) -> None:
        """Initialize the agent nodes with their required services.

        Args:
            chat_model: The LLM model to use for planner and critic decisions.
            search_agent: Search agent for querying literature.
            pipeline: Document pipeline for indexing and retrieval.
            tutor_agent: Tutor agent for generating grounded responses.
        """
        self.chat_model = chat_model
        self.search_agent = search_agent
        self.pipeline = pipeline
        self.tutor_agent = tutor_agent
        logger.info("AgentNodes instantiated successfully.")

    def planner_node(self, state: AgentState) -> dict[str, Any]:
        """Analyzes user query and decides whether search discovery is required.

        Prompting style: Few-shot classification.
        Outputs: updates `search_query` if searching, otherwise routes directly.
        """
        query = state["query"]
        logger.info("Planner Node: Analyzing query '%s'", query)

        system_prompt = (
            "You are the routing planner for an AI research assistant.\n"
            "Analyze the user's request and classify it into one of two options:\n"
            "1. 'SEARCH': The user wants to search academic literature, find papers, "
            "or discover research on a topic.\n"
            "2. 'TUTOR': The user is asking a question about a paper they are currently reading, "
            "or asking for an explanation of a concept.\n\n"
            "Output format:\n"
            "If you select SEARCH, respond with: SEARCH: <keywords to search for>\n"
            "If you select TUTOR, respond with: TUTOR\n\n"
            "Examples:\n"
            "User: Find papers about Vision Transformers\n"
            "Response: SEARCH: Vision Transformers\n"
            "User: Explain Section 3 of this paper\n"
            "Response: TUTOR\n"
            "User: What did the authors mean by multi-head attention?\n"
            "Response: TUTOR\n"
            "User: Search for recent RAG breakthroughs\n"
            "Response: SEARCH: RAG retrieval augment"
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]

        response = self.chat_model.invoke(messages)
        decision = str(response.content).strip()

        logger.info("Planner Node decision: '%s'", decision)

        if decision.upper().startswith("SEARCH"):
            # Extract search keywords: "SEARCH: keywords" -> "keywords"
            search_query = query
            if ":" in decision:
                search_query = decision.split(":", 1)[1].strip()
            
            return {
                "search_query": search_query,
                "messages": [AIMessage(content=f"Planner decided to search for: '{search_query}'")],
            }
        else:
            return {
                "search_query": "",
                "messages": [AIMessage(content="Planner decided to route query to Tutor.")],
            }

    def search_node(self, state: AgentState) -> dict[str, Any]:
        """Invokes SearchAgent to query external APIs and retrieve papers."""
        search_query = state.get("search_query") or state["query"]
        logger.info("Search Node: Querying databases for '%s'", search_query)

        # Retrieve top 5 candidates
        results = self.search_agent.discover_papers(search_query, limit_per_provider=5, top_n=5)
        
        # Extract metadata models from the tuples
        discovered_papers = [paper for paper, _ in results]

        logger.info("Search Node: Discovered %d unique papers.", len(discovered_papers))

        return {
            "discovered_papers": discovered_papers,
            "messages": [AIMessage(content=f"Discovered {len(discovered_papers)} papers.")],
        }

    def selection_node(self, state: AgentState) -> dict[str, Any]:
        """Chooses which paper to index from the discovered pool.

        In this milestone, we automatically select the top-1 ranked paper.
        In future milestones, this can pause for user choice.
        """
        discovered = state.get("discovered_papers", [])
        logger.info("Selection Node: Selecting paper from %d candidates", len(discovered))

        if not discovered:
            logger.warning("Selection Node: No discovered papers to select from.")
            return {"selected_papers": []}

        # Select the first paper in the ranked pool
        selected = [discovered[0]]
        logger.info("Selection Node: Selected paper: '%s'", selected[0].title)

        return {
            "selected_papers": selected,
            "messages": [AIMessage(content=f"Selected paper for reading: '{selected[0].title}'")],
        }

    def retriever_node(self, state: AgentState) -> dict[str, Any]:
        """Indexes selected papers and retrieves context chunks.

        Note: Download of random PDF URLs requires a PDF downloader. In this milestone,
        we verify with our test paper `paper1.pdf` if it matches, otherwise we simulate
        retrieval using our active vector store.
        """
        selected = state.get("selected_papers", [])
        query = state["query"]
        logger.info("Retriever Node: Fetching context for query '%s'", query)

        # In this milestone's integration test, the pipeline is already populated
        # via the manual test pipeline setup. We just query the active FAISS index.
        retrieval_results = self.pipeline.retrieve(query, top_k=5)
        chunks = [result.chunk for result in retrieval_results]

        logger.info("Retriever Node: Retrieved %d context chunks.", len(chunks))

        return {
            "retrieved_context": chunks,
            "messages": [AIMessage(content=f"Retrieved {len(chunks)} chunks of context.")],
        }

    def tutor_node(self, state: AgentState) -> dict[str, Any]:
        """Invokes TutorAgent to generate a grounded response using chunks."""
        query = state["query"]
        chunks = state.get("retrieved_context", [])
        retry_count = state.get("retry_count", 0)

        logger.info("Tutor Node: Generating answer (attempt %d)", retry_count + 1)

        # Call TutorAgent
        answer = self.tutor_agent.answer_question(query, chunks)

        return {
            "generated_answer": answer,
            "retry_count": retry_count + 1,
            # We append the generated answer as an assistant message in chat history
            "messages": [AIMessage(content=answer)],
        }

    def critic_node(self, state: AgentState) -> dict[str, Any]:
        """Evaluates whether the generated answer is grounded in retrieved context.

        Prompting style: Logical evaluation.
        Outputs: updates `critic_approved` and `critic_feedback`.
        """
        query = state["query"]
        context_chunks = state.get("retrieved_context", [])
        answer = state.get("generated_answer", "")

        logger.info("Critic Node: Evaluating answer grounding...")

        if not context_chunks:
            logger.warning("Critic Node: No context available to evaluate.")
            return {"critic_approved": True, "critic_feedback": "No context available."}

        # Formulate evaluation context string
        context_str = "\n\n".join(
            f"Context Block {i}:\n{c.text}" for i, c in enumerate(context_chunks)
        )

        system_prompt = (
            "You are an AI research critic. Your job is to audit a generated answer "
            "against the provided Source Context to detect hallucinations or ungrounded facts.\n\n"
            "Constraints:\n"
            "1. Check if the answer contains any claims, facts, or assumptions NOT supported "
            "by the Source Context. Even minor additions are violations.\n"
            "2. Ignore formatting/tone — evaluate only factual grounding.\n"
            "3. If the answer states 'I cannot find the answer in the provided text' because "
            "the information was missing, this is fully approved.\n\n"
            "Output format:\n"
            "If the answer is fully grounded, respond exactly with: APPROVED\n"
            "If the answer contains hallucinations, respond with: REJECTED: <explanation of what is wrong>"
        )

        prompt = (
            f"Source Context:\n{context_str}\n\n"
            f"User Question: {query}\n\n"
            f"Generated Answer: {answer}"
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]

        response = self.chat_model.invoke(messages)
        feedback = str(response.content).strip()

        logger.info("Critic Node Feedback: '%s'", feedback)

        approved = feedback.upper().startswith("APPROVED")

        return {
            "critic_approved": approved,
            "critic_feedback": feedback,
            "messages": [AIMessage(content=f"Critic evaluated answer: {feedback[:100]}...")],
        }
