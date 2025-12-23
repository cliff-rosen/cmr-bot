"""
Google (Gemini) LLM Provider
"""

import logging
import time
from typing import List, Dict, Optional, AsyncGenerator, Any
import google.genai as genai
import google.genai.types as genai_types

from config.settings import settings
from .base import LLMProvider
from .models import get_model

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 4096


class GoogleProvider(LLMProvider):
    """Provider for Google Gemini models."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Get or create the Google AI client."""
        if self._client is None:
            self._client = genai.Client(api_key=settings.GOOGLE_AI_API_KEY)
        return self._client

    def get_default_model(self) -> str:
        return "gemini-2.5-flash"

    def _adjust_max_tokens_for_reasoning(self, model: str, max_tokens: int) -> int:
        """Reasoning/thinking models need more tokens for internal reasoning."""
        model_config = get_model(model)
        if model_config and model_config.is_reasoning:
            # Use the configured token boost, default to 20x for reasoning models
            boost = model_config.reasoning_token_boost or 20
            return max(max_tokens * boost, 8192)
        return max_tokens

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        try:
            start_time = time.time()
            model = model or self.get_default_model()
            max_tokens = max_tokens or DEFAULT_MAX_TOKENS
            max_tokens = self._adjust_max_tokens_for_reasoning(model, max_tokens)

            client = self._get_client()

            config = genai_types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature if temperature is not None else 0.7
            )

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )

            text = self._extract_text(response)

            self._log_request_stats(
                method="generate",
                model=model,
                start_time=start_time,
                input_tokens=getattr(response.usage_metadata, 'prompt_token_count', 0) if response.usage_metadata else 0,
                output_tokens=getattr(response.usage_metadata, 'candidates_token_count', 0) if response.usage_metadata else 0
            )

            return text

        except Exception as e:
            logger.error(f"Error generating Google response with model {model}: {str(e)}")
            raise

    def _extract_text(self, response) -> str:
        """Extract text from response, handling various response structures."""
        text = ""

        # Try the simple .text accessor first
        try:
            if hasattr(response, 'text') and response.text:
                return response.text.strip()
        except Exception:
            pass

        # Try parsing candidates manually
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    parts = getattr(candidate.content, 'parts', None)
                    if parts:
                        for part in parts:
                            part_text = getattr(part, 'text', None)
                            if part_text:
                                text += part_text
        except Exception:
            pass

        # Check for blocked responses
        if not text:
            try:
                if hasattr(response, 'prompt_feedback'):
                    feedback = response.prompt_feedback
                    block_reason = getattr(feedback, 'block_reason', None)
                    if block_reason:
                        return f"[BLOCKED: {block_reason}]"
            except Exception:
                pass

        return text.strip() if text else "[NO CONTENT]"

    async def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        # Google's streaming is synchronous in the current SDK
        # For now, just yield the full response
        result = await self.generate(prompt, model, max_tokens, temperature)
        yield result

    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        try:
            start_time = time.time()
            model = model or self.get_default_model()
            max_tokens = max_tokens or DEFAULT_MAX_TOKENS
            max_tokens = self._adjust_max_tokens_for_reasoning(model, max_tokens)

            client = self._get_client()

            # Build contents from messages
            contents = []
            if system:
                contents.append({"role": "user", "parts": [{"text": f"System: {system}"}]})
                contents.append({"role": "model", "parts": [{"text": "Understood."}]})

            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

            config = genai_types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature if temperature is not None else 0.7
            )

            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )

            text = self._extract_text(response)

            self._log_request_stats(
                method="chat_completion",
                model=model,
                start_time=start_time,
                input_tokens=getattr(response.usage_metadata, 'prompt_token_count', 0) if response.usage_metadata else 0,
                output_tokens=getattr(response.usage_metadata, 'candidates_token_count', 0) if response.usage_metadata else 0
            )

            return text

        except Exception as e:
            logger.error(f"Error creating Google chat completion with model {model}: {str(e)}")
            raise

    async def create_chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        # For now, just yield the full response
        result = await self.create_chat_completion(messages, model, max_tokens, system, temperature, **kwargs)
        yield result

    async def close(self):
        self._client = None
