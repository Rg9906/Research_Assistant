"""
Unit tests for LangGraph routing functions.

Verifies that the conditional routers (planner_router, critic_router) correctly
evaluate the graph state and return the proper destination node names.
"""

from langgraph.graph import END

from paperpilot.graph.builder import critic_router, planner_router
from paperpilot.graph.state import AgentState


class TestGraphRouters:
    """Unit tests for conditional routing functions."""

    def test_planner_router_selects_search(self):
        """Should route to 'search' if search_query is set in the state."""
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
        )
        assert planner_router(state) == "search"

    def test_planner_router_selects_tutor(self):
        """Should route directly to 'tutor' if search_query is empty."""
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
        )
        assert planner_router(state) == "tutor"

    def test_critic_router_approved(self):
        """Should terminate execution (END) if the critic approved the answer."""
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
        )
        assert critic_router(state) == END

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
        )
        assert critic_router(state) == END
