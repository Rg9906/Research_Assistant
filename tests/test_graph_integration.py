"""Integration tests for the LangGraph multi-agent workflow.

Verifies that the compiled graph executes node functions, processes state transitions,
applies routing loops (Tutor -> Critic), and maintains checkpointer history.
All external models and agents are mocked/stubbed to ensure tests are fast
and do not require internet access or API credentials.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

# We reuse StubChatModel from test_tutor.py
from tests.test_tutor import StubChatModel

from paperpilot.agent.tutor import TutorAgent
from paperpilot.agent.planner import PlannerAgent
from paperpilot.agent.critic import CriticAgent
from paperpilot.core.models import PaperMetadata, PaperSource, TextChunk
from paperpilot.graph.builder import compile_agent_graph
from paperpilot.graph.nodes import AgentNodes
from paperpilot.pipeline import DocumentPipeline
from paperpilot.search.agent import SearchAgent


# ---------------------------------------------------------------------------
# Stub LLM for Routing Decisions
# ---------------------------------------------------------------------------

class GraphStubLLM(StubChatModel):
    """Stub ChatModel that returns predefined routing and evaluation JSON responses."""

    decision: str = "TUTOR"

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        prompt = messages[-1].content
        content = ""

        # Simulate Planner Routing
        if "routing planner" in str(messages[0].content).lower():
            if "search" in prompt.lower() or "find" in prompt.lower():
                if "vision" in prompt.lower():
                    content = """{
                      "difficulty": "graduate/expert",
                      "steps": [
                        {
                          "step_index": 0,
                          "description": "Search for Vision Transformers",
                          "node": "search",
                          "query": "Vision Transformers"
                        },
                        {
                          "step_index": 1,
                          "description": "Explain Vision Transformers",
                          "node": "tutor",
                          "query": "Explain Vision Transformers"
                        }
                      ]
                    }"""
                else:
                    content = """{
                      "difficulty": "graduate/expert",
                      "steps": [
                        {
                          "step_index": 0,
                          "description": "Search for Attention mechanism",
                          "node": "search",
                          "query": "Attention mechanism"
                        },
                        {
                          "step_index": 1,
                          "description": "Explain Attention mechanism",
                          "node": "tutor",
                          "query": "Explain Attention mechanism"
                        }
                      ]
                    }"""
            else:
                content = """{
                  "difficulty": "graduate/expert",
                  "steps": [
                    {
                      "step_index": 0,
                      "description": "Explain concept",
                      "node": "tutor",
                      "query": "Explain concept"
                    }
                  ]
                }"""

        # Simulate Critic Grounding Audit
        elif "critic" in str(messages[0].content).lower():
            if "hallucination" in prompt.lower():
                content = """{
                  "grounding_passed": false,
                  "grounding_feedback": "Hallucination detected",
                  "relevance_passed": true,
                  "relevance_feedback": "Relevant",
                  "style_passed": true,
                  "style_feedback": "Correct style",
                  "approved": false,
                  "feedback": "REJECTED: Hallucination detected"
                }"""
            else:
                content = """{
                  "grounding_passed": true,
                  "grounding_feedback": "Supported",
                  "relevance_passed": true,
                  "relevance_feedback": "Relevant",
                  "style_passed": true,
                  "style_feedback": "Correct style",
                  "approved": true,
                  "feedback": "APPROVED"
                }"""
        else:
            content = self.decision

        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGraphIntegration:
    """Integration tests for the compiled agent graph."""

    def test_compile_graph(self):
        """Should compile the StateGraph successfully without raising errors."""
        mock_llm = GraphStubLLM()
        mock_search = MagicMock(spec=SearchAgent)
        mock_pipeline = MagicMock(spec=DocumentPipeline)
        mock_tutor = MagicMock(spec=TutorAgent)

        nodes = AgentNodes(
            chat_model=mock_llm,
            search_agent=mock_search,
            pipeline=mock_pipeline,
            tutor_agent=mock_tutor,
        )

        graph = compile_agent_graph(nodes)
        assert graph is not None

    def test_direct_tutor_routing_flow(self):
        """If user query is about an existing paper, should bypass search and invoke tutor & critic."""
        mock_llm = GraphStubLLM()
        
        # Mock SearchAgent (should not be called)
        mock_search = MagicMock(spec=SearchAgent)
        
        # Mock DocumentPipeline (returns a dummy chunk)
        mock_pipeline = MagicMock(spec=DocumentPipeline)
        dummy_chunk = TextChunk(paper_id=uuid4(), chunk_index=0, text="Attention is all you need.", char_count=26)
        mock_pipeline.retrieve.return_value = [
            MagicMock(chunk=dummy_chunk, score=0.1, rank=1)
        ]
        
        # Mock TutorAgent (returns a dummy answer)
        mock_tutor = MagicMock(spec=TutorAgent)
        mock_tutor.answer_question.return_value = "The paper proposes self-attention."

        nodes = AgentNodes(
            chat_model=mock_llm,
            search_agent=mock_search,
            pipeline=mock_pipeline,
            tutor_agent=mock_tutor,
        )

        graph = compile_agent_graph(nodes)

        # Run Graph
        inputs = {
            "query": "Explain the attention mechanism in this paper.",
            "messages": [],
            "discovered_papers": [],
            "selected_papers": [],
            "retrieved_context": [],
            "generated_answer": "",
            "critic_feedback": "",
            "critic_approved": False,
            "retry_count": 0,
            "plan_steps": [],
            "plan_nodes": [],
            "plan_queries": [],
            "current_step_idx": 0,
            "step_answers": [],
            "tutor_difficulty": "graduate/expert",
        }
        
        config = {"configurable": {"thread_id": "test_thread_1"}}
        outputs = graph.invoke(inputs, config=config)

        # Verifications
        assert len(outputs["discovered_papers"]) == 0
        assert len(outputs["retrieved_context"]) == 1
        assert outputs["generated_answer"] == "The paper proposes self-attention."
        assert outputs["critic_approved"] is True
        assert outputs["retry_count"] == 1
        
        # SearchAgent should NOT have been invoked
        mock_search.discover_papers.assert_not_called()
        # TutorAgent should have been invoked once
        mock_tutor.answer_question.assert_called_once()

    def test_search_and_retrieve_flow(self):
        """If user query asks for discovery, should run search, select, process, tutor, and critic."""
        mock_llm = GraphStubLLM()
        
        # Mock SearchAgent
        mock_search = MagicMock(spec=SearchAgent)
        dummy_paper = PaperMetadata(title="Vision Transformers", source=PaperSource.ARXIV)
        mock_search.discover_papers.return_value = [(dummy_paper, 1.0)]

        # Mock DocumentPipeline
        mock_pipeline = MagicMock(spec=DocumentPipeline)
        dummy_chunk = TextChunk(paper_id=dummy_paper.paper_id, chunk_index=0, text="ViT paper...", char_count=12)
        mock_pipeline.retrieve.return_value = [
            MagicMock(chunk=dummy_chunk, score=0.1, rank=1)
        ]
        
        # Mock TutorAgent
        mock_tutor = MagicMock(spec=TutorAgent)
        mock_tutor.answer_question.return_value = "ViT applies transformers to image patches."

        nodes = AgentNodes(
            chat_model=mock_llm,
            search_agent=mock_search,
            pipeline=mock_pipeline,
            tutor_agent=mock_tutor,
        )

        graph = compile_agent_graph(nodes)

        inputs = {
            "query": "Find and explain papers about Vision Transformers.",
            "messages": [],
            "discovered_papers": [],
            "selected_papers": [],
            "retrieved_context": [],
            "generated_answer": "",
            "critic_feedback": "",
            "critic_approved": False,
            "retry_count": 0,
            "plan_steps": [],
            "plan_nodes": [],
            "plan_queries": [],
            "current_step_idx": 0,
            "step_answers": [],
            "tutor_difficulty": "graduate/expert",
        }
        
        config = {"configurable": {"thread_id": "test_thread_2"}}
        outputs = graph.invoke(inputs, config=config)

        # Verifications
        assert "Vision Transformers" in outputs["search_query"]
        assert len(outputs["discovered_papers"]) == 1
        assert outputs["discovered_papers"][0].title == "Vision Transformers"
        assert len(outputs["selected_papers"]) == 1
        assert outputs["selected_papers"][0].title == "Vision Transformers"
        assert len(outputs["retrieved_context"]) == 1
        assert outputs["generated_answer"] == "ViT applies transformers to image patches."
        assert outputs["critic_approved"] is True

        # Assert search was called
        mock_search.discover_papers.assert_called_once()
