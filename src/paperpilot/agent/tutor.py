"""
Tutor Agent for guiding users through research papers.

This module implements the TutorAgent, which is responsible for answering
user questions about a research paper. It uses a ChatModel to generate
answers that are strictly grounded in retrieved source context.

Why strict grounding?
    LLMs are trained to be helpful and creative, which makes them prone to
    hallucinating details that sound plausible but are not present in the
    source text. For scientific literature, this is unacceptable. Answers
    must be fully factual and traceable back to the source text.

    To enforce this, we:
    1. Structure the prompt to explicitly demand that the model only answer
       using the provided context.
    2. Provide a standard "refusal string" ("I cannot find the answer in the
       provided text.") that the model must output if the answer is missing.
    3. Set model temperature to 0.0, which makes token generation deterministic
       and minimizes creative interpolation.

Why use BaseChatModel?
    By type-hinting against langchain_core.language_models.BaseChatModel,
    the TutorAgent is decoupled from specific providers (OpenAI, Gemini, Anthropic, Ollama).
    As long as the model implements LangChain's BaseChatModel interface, it works.
"""

from __future__ import annotations

import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from paperpilot.core.models import TextChunk

logger = logging.getLogger(__name__)

# Standard instruction block to enforce strict context-grounding
SYSTEM_PROMPT_TEMPLATE = (
    "You are a graduate-level AI research tutor. Your job is to answer questions "
    "about a research paper using ONLY the provided Source Context blocks.\n\n"
    "Constraints:\n"
    "1. Rely ONLY on the clear facts mentioned in the context. Do not assume, extrapolate, "
    "or use outside knowledge.\n"
    "2. If the context does not contain enough information to answer the question completely "
    "and accurately, reply exactly with: 'I cannot find the answer in the provided text.'\n"
    "3. Do not make up explanations or mention any facts not explicitly stated in the context.\n"
    "4. Keep your answers technically precise, factual, and concise.\n"
    "5. When reference details are available (such as page numbers), cite them in your response "
    "(e.g., [Page 3]).\n\n"
    "Source Context:\n"
    "=========================================\n"
    "{context}\n"
    "========================================="
)


class TutorAgent:
    """Tutor Agent that answers questions about a paper using grounded context.

    This agent acts as the generation step of our RAG engine. It accepts
    retrieved TextChunks, builds a grounded system prompt, and queries the LLM.

    Attributes:
        chat_model: The LangChain ChatModel instance used for generation.
        refusal_response: The standard string the model outputs when the answer
                          cannot be found in the context.
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        refusal_response: str = "I cannot find the answer in the provided text.",
    ) -> None:
        """Initialize the Tutor Agent.

        Args:
            chat_model: Any ChatModel implementing LangChain's BaseChatModel.
            refusal_response: The expected fallback response when context is insufficient.
        """
        self.chat_model = chat_model
        self.refusal_response = refusal_response
        logger.info("TutorAgent initialized with model: %s", type(chat_model).__name__)

    def answer_question(
        self,
        question: str,
        chunks: list[TextChunk],
    ) -> str:
        """Answer a user question grounded in the provided chunks.

        Steps:
        1. Format the TextChunks into a structured context string.
        2. Build SystemMessage (grounding prompt + context) and HumanMessage (question).
        3. Invoke the ChatModel.
        4. Return the text response.

        Args:
            question: The user's natural language question.
            chunks: List of retrieved TextChunks to use as grounding context.

        Returns:
            The model's textual answer.
        """
        if not chunks:
            logger.warning("No context chunks provided for answering question.")
            return self.refusal_response

        # Format context: label each chunk with index and source page if available
        formatted_blocks = []
        for chunk in chunks:
            page_info = f" (Page {chunk.start_page})" if chunk.start_page else ""
            block = f"Chunk {chunk.chunk_index}{page_info}:\n{chunk.text.strip()}"
            formatted_blocks.append(block)
        
        context_str = "\n\n-----------------------------------------\n\n".join(formatted_blocks)
        
        # Build prompt
        system_text = SYSTEM_PROMPT_TEMPLATE.format(context=context_str)
        messages = [
            SystemMessage(content=system_text),
            HumanMessage(content=question),
        ]

        logger.debug("TutorAgent invoking ChatModel with %d context chunks", len(chunks))
        
        try:
            # Invoke model (sync call)
            response = self.chat_model.invoke(messages)
            answer = response.content
            
            # Type safety check: LangChain content can be str or list of dicts (multimodal)
            if not isinstance(answer, str):
                answer = str(answer)

            # Post-process response: strip whitespace
            answer = answer.strip()
            
            logger.info("TutorAgent generated answer (%d chars)", len(answer))
            return answer

        except Exception as e:
            logger.error("TutorAgent failed to generate response: %s", e)
            raise e
