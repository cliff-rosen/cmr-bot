from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, AsyncGenerator
from dataclasses import dataclass
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMTestResponse:
    """Response from LLM testing methods."""
    text: str
    model_id: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[int] = None


class LLMProvider(ABC):
    """Base class for LLM providers"""

    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider"""
        pass

    @abstractmethod
    async def generate(self,
                       prompt: str,
                       model: Optional[str] = None,
                       max_tokens: Optional[int] = None
                       ) -> str:
        """Generate a response from the LLM"""
        pass

    @abstractmethod
    async def generate_stream(self,
                             prompt: str,
                             model: Optional[str] = None,
                             max_tokens: Optional[int] = None
                             ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM"""
        pass

    @abstractmethod
    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> str:
        """Create a chat completion with the given messages"""
        raise NotImplementedError

    @abstractmethod
    async def create_chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Create a streaming chat completion with the given messages"""
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        """Cleanup resources"""
        pass

    async def complete_multi_question(
        self,
        model_id: str,
        context: str,
        questions: List[str],
        max_tokens: int = 2000,
        temperature: float = 0.0
    ) -> LLMTestResponse:
        """
        Send context with multiple questions and get responses.
        Used by LLM testing tool to test how models handle cognitive load.

        Args:
            model_id: The model ID to use
            context: The context/instructions
            questions: List of questions to answer
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            LLMTestResponse with the model's text response containing all answers
        """
        start_time = time.time()

        # Build prompt with numbered questions
        questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        prompt = f"""{context}

        Questions:

        {questions_text}"""

        # Use the existing generate method
        text = await self.generate(
            prompt=prompt,
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return LLMTestResponse(
            text=text.strip() if text else "",
            model_id=model_id,
            latency_ms=latency_ms
        )

    def _log_request_stats(self,
                           method: str,
                           model: str,
                           start_time: float,
                           input_tokens: int,
                           output_tokens: int):
        duration = time.time() - start_time
        logger.info(
            f"LLM Request Stats - Method: {method}, Model: {model}, "
            f"Duration: {duration:.2f}s, Input Tokens: {input_tokens}, "
            f"Output Tokens: {output_tokens}, Total Tokens: {input_tokens + output_tokens}"
        )
