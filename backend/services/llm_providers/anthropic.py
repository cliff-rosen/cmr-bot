"""
Anthropic (Claude) LLM Provider
"""

import time
from typing import List, Optional
import anthropic

from config.settings import settings
from .base import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    """Provider for Anthropic Claude models."""

    @property
    def name(self) -> str:
        return "anthropic"

    def is_configured(self) -> bool:
        """Check if Anthropic API key is configured."""
        return bool(settings.ANTHROPIC_API_KEY)

    def get_api_key(self) -> Optional[str]:
        """Get the Anthropic API key from settings."""
        return settings.ANTHROPIC_API_KEY

    def _get_client(self) -> anthropic.Anthropic:
        """Get an Anthropic client instance."""
        return anthropic.Anthropic(api_key=self.get_api_key())

    async def complete(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0
    ) -> LLMResponse:
        """Send a prompt to Claude and get a response."""
        start_time = time.time()
        client = self._get_client()

        response = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text from response
        text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                text += block.text

        latency_ms = int((time.time() - start_time) * 1000)

        return LLMResponse(
            text=text.strip(),
            model_id=model_id,
            input_tokens=response.usage.input_tokens if response.usage else None,
            output_tokens=response.usage.output_tokens if response.usage else None,
            latency_ms=latency_ms
        )

    async def complete_multi_question(
        self,
        model_id: str,
        context: str,
        questions: List[str],
        max_tokens: int = 500,
        temperature: float = 0.0
    ) -> LLMResponse:
        """Send context with multiple questions to Claude."""
        # Build prompt with numbered questions
        questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        prompt = f"""{context}

Questions:

{questions_text}"""

        return await self.complete(model_id, prompt, max_tokens, temperature)
