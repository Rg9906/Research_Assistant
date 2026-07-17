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
from paperpilot.agent.planner import PlannerAgent
from paperpilot.agent.critic import CriticAgent
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
        planner_agent: PlannerAgent | None = None,
        critic_agent: CriticAgent | None = None,
    ) -> None:
        """Initialize the agent nodes with their required services.

        Args:
            chat_model: The LLM model to use for planner and critic decisions.
            search_agent: Search agent for querying literature.
            pipeline: Document pipeline for indexing and retrieval.
            tutor_agent: Tutor agent for generating grounded responses.
            planner_agent: Optional PlannerAgent. Created from chat_model if missing.
            critic_agent: Optional CriticAgent. Created from chat_model if missing.
        """
        self.chat_model = chat_model
        self.search_agent = search_agent
        self.pipeline = pipeline
        self.tutor_agent = tutor_agent
        self.planner_agent = planner_agent or PlannerAgent(chat_model)
        self.critic_agent = critic_agent or CriticAgent(chat_model)
        logger.info("AgentNodes instantiated successfully.")

    def planner_node(self, state: AgentState) -> dict[str, Any]:
        """Analyzes user query and formulates a multi-step execution plan."""
        query = state["query"]
        logger.info("Planner Node: Analyzing query '%s'", query)

        plan = self.planner_agent.generate_plan(query)

        # Get first step node and query to decide initial search/tutor routing
        first_step_node = plan.steps[0].node if plan.steps else "tutor"
        first_step_query = plan.steps[0].query if plan.steps else query

        search_query = first_step_query if first_step_node == "search" else ""

        plan_steps = [step.description for step in plan.steps]
        plan_nodes = [step.node for step in plan.steps]
        plan_queries = [step.query for step in plan.steps]

        logger.info("Planner Node: generated plan difficulty = %s", plan.difficulty)
        for i, step in enumerate(plan.steps):
            logger.info("  Step %d [%s]: %s", i, step.node, step.description)

        return {
            "plan_steps": plan_steps,
            "plan_nodes": plan_nodes,
            "plan_queries": plan_queries,
            "current_step_idx": 0,
            "step_answers": [],
            "tutor_difficulty": plan.difficulty,
            "search_query": search_query,
            "messages": [AIMessage(content=f"Planner generated plan with {len(plan_steps)} steps. Difficulty: {plan.difficulty}")],
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
        """Indexes selected papers and retrieves context chunks."""
        selected = state.get("selected_papers", [])

        current_idx = state.get("current_step_idx", 0)
        plan_nodes = state.get("plan_nodes", [])
        plan_queries = state.get("plan_queries", [])

        # If we entered here from a 'search' node flow, the indexing is complete.
        # Advance the step index to the next tutor step.
        if current_idx < len(plan_nodes) and plan_nodes[current_idx] == "search":
            current_idx += 1
            logger.info("Retriever Node: completed search step. Advancing current_step_idx to %d", current_idx)

        # Determine active query/subquestion
        if current_idx < len(plan_queries):
            active_query = plan_queries[current_idx]
        else:
            active_query = state["query"]

        logger.info("Retriever Node: Fetching context for query '%s'", active_query)

        # Query the active FAISS index
        retrieval_results = self.pipeline.retrieve(active_query, top_k=5)
        chunks = [result.chunk for result in retrieval_results]

        logger.info("Retriever Node: Retrieved %d context chunks.", len(chunks))

        return {
            "retrieved_context": chunks,
            "current_step_idx": current_idx,
            "messages": [AIMessage(content=f"Retrieved {len(chunks)} chunks of context for: '{active_query}'")],
        }

    def tutor_node(self, state: AgentState) -> dict[str, Any]:
        """Invokes TutorAgent to generate a grounded response using chunks."""
        current_idx = state.get("current_step_idx", 0)
        plan_queries = state.get("plan_queries", [])
        difficulty = state.get("tutor_difficulty", "graduate/expert")
        chunks = state.get("retrieved_context", [])
        retry_count = state.get("retry_count", 0)

        if current_idx < len(plan_queries):
            active_query = plan_queries[current_idx]
        else:
            active_query = state["query"]

        logger.info("Tutor Node: Generating answer for '%s' (difficulty=%s, attempt %d)", active_query, difficulty, retry_count + 1)

        # Call TutorAgent
        answer = self.tutor_agent.answer_question(active_query, chunks, difficulty=difficulty)

        return {
            "generated_answer": answer,
            "retry_count": retry_count + 1,
            "critic_approved": False, # Reset grounding approval for this new answer draft
            "messages": [AIMessage(content=answer)],
        }

    def critic_node(self, state: AgentState) -> dict[str, Any]:
        """Evaluates whether the generated answer is grounded, relevant, and formatted correctly."""
        current_idx = state.get("current_step_idx", 0)
        plan_nodes = state.get("plan_nodes", [])
        plan_queries = state.get("plan_queries", [])
        difficulty = state.get("tutor_difficulty", "graduate/expert")
        context_chunks = state.get("retrieved_context", [])
        answer = state.get("generated_answer", "")

        if current_idx < len(plan_queries):
            active_query = plan_queries[current_idx]
        else:
            active_query = state["query"]

        logger.info("Critic Node: Evaluating answer for step %d...", current_idx)

        # Call CriticAgent
        report = self.critic_agent.evaluate_answer(active_query, context_chunks, answer, difficulty)

        updates: dict[str, Any] = {
            "critic_feedback": report.feedback,
        }

        if report.approved:
            step_answers = list(state.get("step_answers", []))
            step_answers.append(answer)
            updates["step_answers"] = step_answers
            updates["current_step_idx"] = current_idx + 1

            if current_idx + 1 < len(plan_nodes):
                updates["retry_count"] = 0 # Reset retry count for next step
                updates["critic_approved"] = True
            else:
                # Compile final answer from all step answers
                if len(step_answers) > 1:
                    final_answer = ""
                    for idx, (desc, ans) in enumerate(zip(state.get("plan_steps", []), step_answers)):
                        final_answer += f"### Step {idx+1}: {desc}\n{ans}\n\n"
                    updates["generated_answer"] = final_answer.strip()
                else:
                    updates["generated_answer"] = answer
                updates["critic_approved"] = True
        else:
            updates["critic_approved"] = False

        return updates
