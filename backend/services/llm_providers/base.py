"""
Base class for LLM providers.

Each provider (Anthropic, OpenAI, Google) implements this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from config.settings import settings


@dataclass
class LLMResponse:
    """Standard response from any LLM provider."""
    text: str
    model_id: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[int] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'anthropic', 'openai', 'google')."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider has an API key configured."""
        pass

    @abstractmethod
    def get_api_key(self) -> Optional[str]:
        """Get the API key from settings."""
        pass

    @abstractmethod
    async def complete(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0
    ) -> LLMResponse:
        """
        Send a prompt to the model and get a response.

        Args:
            model_id: The API model ID to use
            prompt: The prompt to send
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0 = deterministic)

        Returns:
            LLMResponse with the model's text response
        """
        pass

    @abstractmethod
    async def complete_multi_question(
        self,
        model_id: str,
        context: str,
        questions: List[str],
        max_tokens: int = 500,
        temperature: float = 0.0
    ) -> LLMResponse:
        """
        Send a context with multiple questions and get responses.

        This is the main method used for LLM testing - sends all questions
        at once to test how the model handles the cognitive load.

        Args:
            model_id: The API model ID to use
            context: The context/instructions
            questions: List of questions to answer
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            LLMResponse with the model's text response containing all answers
        """
        pass
