"""
Unit tests for the Tutor Agent.

These tests use a mock/fake ChatModel to verify that the TutorAgent formats the
grounding prompt correctly, structures messages, handles page citations, and
returns correct responses without making actual external API calls.
"""

from uuid import uuid4

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from paperpilot.agent.tutor import SYSTEM_PROMPT_TEMPLATE, TutorAgent
from paperpilot.core.models import TextChunk


# ---------------------------------------------------------------------------
# Simple Stub ChatModel
# ---------------------------------------------------------------------------

class StubChatModel(BaseChatModel):
    """A minimal mock ChatModel that returns predefined messages.

    It captures the list of messages passed to its invoke() method so we can
    inspect them in tests.
    """

    response_text: str = "Test response"
    captured_messages: list[BaseMessage] = []

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        # Capture messages for test assertions
        self.captured_messages.clear()
        self.captured_messages.extend(messages)
        
        # Return structured generation
        message = AIMessage(content=self.response_text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "stub-chat-model"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTutorAgent:
    """Unit tests for the TutorAgent class."""

    def test_answer_question_sends_correct_messages(self):
        """TutorAgent should format context into a SystemMessage and question into a HumanMessage."""
        model = StubChatModel(response_text="According to the text, transformers use self-attention.")
        agent = TutorAgent(chat_model=model)

        chunks = [
            TextChunk(
                paper_id=uuid4(),
                chunk_index=0,
                text="Transformers were introduced in 2017.",
                char_count=36,
                start_page=1,
            ),
            TextChunk(
                paper_id=uuid4(),
                chunk_index=1,
                text="They rely entirely on self-attention.",
                char_count=37,
                start_page=2,
            ),
        ]

        question = "What mechanisms do transformers use?"
        answer = agent.answer_question(question, chunks)

        assert answer == "According to the text, transformers use self-attention."
        assert len(model.captured_messages) == 2
        
        # Verify message types
        assert isinstance(model.captured_messages[0], SystemMessage)
        assert isinstance(model.captured_messages[1], HumanMessage)

        # Verify system prompt content contains context
        system_text = model.captured_messages[0].content
        assert "Transformers were introduced in 2017." in system_text
        assert "They rely entirely on self-attention." in system_text
        assert "Chunk 0" in system_text
        assert "Page 1" in system_text
        assert "Chunk 1" in system_text
        assert "Page 2" in system_text

        # Verify human message content matches question
        assert model.captured_messages[1].content == question

    def test_refuses_when_empty_context_provided(self):
        """If an empty chunk list is provided, should immediately return refusal response without LLM call."""
        model = StubChatModel()
        refusal_msg = "Context is empty, cannot answer."
        agent = TutorAgent(chat_model=model, refusal_response=refusal_msg)

        answer = agent.answer_question("Where is page 4?", chunks=[])

        # Verification
        assert answer == refusal_msg
        assert len(model.captured_messages) == 0  # No LLM invocation should happen

    def test_strips_output_whitespace(self):
        """The agent should strip leading/trailing whitespace from the LLM's response."""
        model = StubChatModel(response_text="   Clean Answer \n  ")
        agent = TutorAgent(chat_model=model)

        answer = agent.answer_question("test?", [
            TextChunk(paper_id=uuid4(), chunk_index=0, text="dummy", char_count=5)
        ])

        assert answer == "Clean Answer"
