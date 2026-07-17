"""Unit tests for LangGraph routing functions.

Verifies that the conditional routers (planner_router, critic_router) correctly
evaluate the graph state and return the proper destination node names.
"""

from langgraph.graph import END

from paperpilot.graph.builder import critic_router, planner_router
from paperpilot.graph.state import AgentState


class TestGraphRouters:
    """Unit tests for conditional routing functions."""

    def test_planner_router_selects_search(self):
        """Should route to 'search' if current step in plan points to search."""
        state = AgentState(
            query="Find papers about transformers",
            search_query="transformers",
            discovered_papers=[],
            selected_papers=[],
            retrieved_context=[],
            generated_answer="",
            critic_feedback="",
            critic_approved=False,
            retry_count=0,
            messages=[],
            plan_steps=["Search papers"],
            plan_nodes=["search"],
            plan_queries=["transformers"],
            current_step_idx=0,
            step_answers=[],
            tutor_difficulty="graduate/expert",
        )
        assert planner_router(state) == "search"

    def test_planner_router_selects_tutor(self):
        """Should route directly to 'tutor' (retriever) if current step in plan points to tutor."""
        state = AgentState(
            query="Explain self-attention",
            search_query="",
            discovered_papers=[],
            selected_papers=[],
            retrieved_context=[],
            generated_answer="",
            critic_feedback="",
            critic_approved=False,
            retry_count=0,
            messages=[],
            plan_steps=["Explain self-attention"],
            plan_nodes=["tutor"],
            plan_queries=["self-attention"],
            current_step_idx=0,
            step_answers=[],
            tutor_difficulty="graduate/expert",
        )
        assert planner_router(state) == "tutor"

    def test_critic_router_approved_final_step(self):
        """Should terminate execution (END) if the critic approved the final step in the plan."""
        state = AgentState(
            query="Explain self-attention",
            search_query="",
            discovered_papers=[],
            selected_papers=[],
            retrieved_context=[],
            generated_answer="Self-attention allows tokens to look at each other.",
            critic_feedback="Approved",
            critic_approved=True,
            retry_count=1,
            messages=[],
            plan_steps=["Explain self-attention"],
            plan_nodes=["tutor"],
            plan_queries=["self-attention"],
            current_step_idx=1,  # Incremented to 1 (which equals len of plan_nodes)
            step_answers=["Self-attention allows tokens to look at each other."],
            tutor_difficulty="graduate/expert",
        )
        assert critic_router(state) == END

    def test_critic_router_approved_non_final_step(self):
        """Should route to 'retriever' if approved but there are more steps remaining in the plan."""
        state = AgentState(
            query="Explain self-attention and compare with CNN",
            search_query="",
            discovered_papers=[],
            selected_papers=[],
            retrieved_context=[],
            generated_answer="Self-attention explanation.",
            critic_feedback="Approved",
            critic_approved=True,
            retry_count=1,
            messages=[],
            plan_steps=["Explain self-attention", "Compare with CNN"],
            plan_nodes=["tutor", "tutor"],
            plan_queries=["self-attention", "comparison"],
            current_step_idx=1,  # Step 0 approved, so incremented to 1. 1 < 2, so more steps remain.
            step_answers=["Self-attention explanation."],
            tutor_difficulty="graduate/expert",
        )
        assert critic_router(state) == "retriever"

    def test_critic_router_rejected_retries(self):
        """Should loop back to 'tutor' if rejected and retry_count < 3."""
        state = AgentState(
            query="Explain self-attention",
            search_query="",
            discovered_papers=[],
            selected_papers=[],
            retrieved_context=[],
            generated_answer="Gargantuan claim.",
            critic_feedback="Rejected: Unfounded claim",
            critic_approved=False,
            retry_count=2,  # 2 retries completed
            messages=[],
            plan_steps=["Explain self-attention"],
            plan_nodes=["tutor"],
            plan_queries=["self-attention"],
            current_step_idx=0,
            step_answers=[],
            tutor_difficulty="graduate/expert",
        )
        assert critic_router(state) == "tutor"

    def test_critic_router_rejected_max_retries(self):
        """Should terminate execution (END) if rejected but retry_count reached 3."""
        state = AgentState(
            query="Explain self-attention",
            search_query="",
            discovered_papers=[],
            selected_papers=[],
            retrieved_context=[],
            generated_answer="Incorrect claim.",
            critic_feedback="Rejected again",
            critic_approved=False,
            retry_count=3,  # Max retries reached
            messages=[],
            plan_steps=["Explain self-attention"],
            plan_nodes=["tutor"],
            plan_queries=["self-attention"],
            current_step_idx=0,
            step_answers=[],
            tutor_difficulty="graduate/expert",
        )
        assert critic_router(state) == END
