"""
Graph builder and compiler for PaperPilot AI.

This module assembles the LangGraph StateGraph, registers the nodes, defines
the conditional routing edges (loops & branching), and compiles the workflow
with in-memory persistence.
"""

from __future__ import annotations

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from paperpilot.graph.nodes import AgentNodes
from paperpilot.graph.state import AgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routing Routers (Conditional Edges)
# ---------------------------------------------------------------------------

def planner_router(state: AgentState) -> str:
    """Determine whether search is required or if we route directly to tutoring.

    Args:
        state: Shared graph state.

    Returns:
        The name of the next node ("search" or "tutor").
    """
    plan_nodes = state.get("plan_nodes", [])
    current_idx = state.get("current_step_idx", 0)

    if current_idx < len(plan_nodes):
        node = plan_nodes[current_idx]
        if node == "search":
            return "search"
    return "tutor"


def critic_router(state: AgentState) -> str:
    """Evaluate Critic approval. Decide to retry, continue to next step, or finalize.

    Loops back to Tutor if the response was rejected, up to a limit of 3 tries.
    If approved and there are more plan steps, routes to retriever for the next step.

    Args:
        state: Shared graph state.

    Returns:
        The next node location ("tutor", "retriever", or END).
    """
    approved = state.get("critic_approved", False)
    retry_count = state.get("retry_count", 0)
    current_idx = state.get("current_step_idx", 0)
    plan_nodes = state.get("plan_nodes", [])

    if approved:
        if current_idx < len(plan_nodes):
            logger.info("Step approved. Routing to retriever for next step (%d/%d).", current_idx, len(plan_nodes))
            return "retriever"
        else:
            logger.info("Critic approved final answer. Finalizing graph execution.")
            return END

    if retry_count < 3:
        logger.info(
            "Critic REJECTED answer. Retrying generation (retry_count=%d/3)",
            retry_count,
        )
        return "tutor"

    logger.warning("Critic REJECTED answer, but max retries reached. Exiting graph.")
    return END


# ---------------------------------------------------------------------------
# Graph Constructor
# ---------------------------------------------------------------------------

def create_agent_graph(nodes: AgentNodes) -> StateGraph:
    """Assemble and construct the StateGraph workflow.

    Args:
        nodes: An initialized AgentNodes instance.

    Returns:
        An uncompiled StateGraph instance.
    """
    # 1. Instantiate state graph
    workflow = StateGraph(AgentState)

    # 2. Register nodes
    workflow.add_node("planner", nodes.planner_node)
    workflow.add_node("search", nodes.search_node)
    workflow.add_node("selection", nodes.selection_node)
    workflow.add_node("retriever", nodes.retriever_node)
    workflow.add_node("tutor", nodes.tutor_node)
    workflow.add_node("critic", nodes.critic_node)

    # 3. Register edges (Control Flow)
    
    # Entry edge
    workflow.add_edge(START, "planner")

    # Planner branching: routes to search or directly to tutor
    workflow.add_conditional_edges(
        "planner",
        planner_router,
        {
            "search": "search",
            "tutor": "retriever",
        },
    )

    # Search flow
    workflow.add_edge("search", "selection")
    workflow.add_edge("selection", "retriever")
    workflow.add_edge("retriever", "tutor")

    # Tutor output -> Critic audit
    workflow.add_edge("tutor", "critic")

    # Critic routing: loop back to tutor, move to next step via retriever, or finish
    workflow.add_conditional_edges(
        "critic",
        critic_router,
        {
            "tutor": "tutor",
            "retriever": "retriever",
            END: END,
        },
    )

    logger.info("LangGraph workflow assembled.")
    return workflow


def compile_agent_graph(nodes: AgentNodes) -> Any:
    """Build and compile the multi-agent graph with in-memory checkpointer.

    This returns the compiled graph executable.

    Args:
        nodes: An initialized AgentNodes instance.

    Returns:
        The compiled Graph object ready to invoke.
    """
    workflow = create_agent_graph(nodes)
    
    # Use MemorySaver checkpointer for state persistence
    checkpointer = MemorySaver()
    compiled_graph = workflow.compile(checkpointer=checkpointer)

    logger.info("LangGraph workflow compiled with MemorySaver checkpointer.")
    return compiled_graph
