"""
OpenAI (GPT) LLM Provider
"""

import time
from typing import List, Optional
from openai import OpenAI

from config.settings import settings
from .base import LLMProvider, LLMResponse
from .models import get_model, ModelConfig


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI GPT and o-series models."""

    @property
    def name(self) -> str:
        return "openai"

    def is_configured(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(settings.OPENAI_API_KEY)

    def get_api_key(self) -> Optional[str]:
        """Get the OpenAI API key from settings."""
        return settings.OPENAI_API_KEY

    def _get_client(self) -> OpenAI:
        """Get an OpenAI client instance."""
        return OpenAI(api_key=self.get_api_key())

    async def complete(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0,
        model_config: Optional[ModelConfig] = None
    ) -> LLMResponse:
        """Send a prompt to OpenAI and get a response."""
        start_time = time.time()
        client = self._get_client()

        # Get model config if not provided
        if model_config is None:
            model_config = get_model(model_id)

        # Build parameters based on model capabilities
        params = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}]
        }

        # Handle max tokens parameter (different name for newer models)
        if model_config and model_config.uses_max_completion_tokens:
            params["max_completion_tokens"] = max_tokens
        else:
            params["max_tokens"] = max_tokens

        # Handle temperature (not supported by reasoning models)
        if model_config is None or model_config.supports_temperature:
            params["temperature"] = temperature

        # Handle reasoning effort for o3 models
        if model_config and model_config.supports_reasoning_effort and model_config.default_reasoning_effort:
            params["reasoning_effort"] = model_config.default_reasoning_effort

        response = client.chat.completions.create(**params)

        text = response.choices[0].message.content or ""
        latency_ms = int((time.time() - start_time) * 1000)

        return LLMResponse(
            text=text.strip(),
            model_id=model_id,
            input_tokens=response.usage.prompt_tokens if response.usage else None,
            output_tokens=response.usage.completion_tokens if response.usage else None,
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
        """Send context with multiple questions to OpenAI."""
        # Build prompt with numbered questions
        questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        prompt = f"""{context}

Questions:

{questions_text}"""

        # Get model config once and pass to complete
        model_config = get_model(model_id)
        return await self.complete(model_id, prompt, max_tokens, temperature, model_config)
