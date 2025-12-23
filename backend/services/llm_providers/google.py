"""
Google (Gemini) LLM Provider
"""

import time
from typing import List, Optional
import google.genai as genai
import google.genai.types as genai_types

from config.settings import settings
from .base import LLMProvider, LLMResponse


class GoogleProvider(LLMProvider):
    """Provider for Google Gemini models."""

    _client = None

    @property
    def name(self) -> str:
        return "google"

    def is_configured(self) -> bool:
        """Check if Google AI API key is configured."""
        return bool(settings.GOOGLE_AI_API_KEY)

    def get_api_key(self) -> Optional[str]:
        """Get the Google AI API key from settings."""
        return settings.GOOGLE_AI_API_KEY

    def _get_client(self):
        """Get or create the Google AI client."""
        if self._client is None:
            self._client = genai.Client(api_key=self.get_api_key())
        return self._client

    async def complete(
        self,
        model_id: str,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0
    ) -> LLMResponse:
        """Send a prompt to Gemini and get a response."""
        start_time = time.time()
        client = self._get_client()

        # Configure generation
        config = genai_types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature
        )

        # Generate response
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=config
        )

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract text - handle different response structures
        text = ""
        if hasattr(response, 'text') and response.text:
            text = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            # Try to get text from candidates
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                for part in candidate.content.parts:
                    if hasattr(part, 'text'):
                        text += part.text

        # Check for blocked responses
        if not text and hasattr(response, 'prompt_feedback'):
            feedback = response.prompt_feedback
            if hasattr(feedback, 'block_reason') and feedback.block_reason:
                text = f"[BLOCKED: {feedback.block_reason}]"

        # Try to get token counts if available
        input_tokens = None
        output_tokens = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', None)
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', None)

        return LLMResponse(
            text=text.strip(),
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
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
        """Send context with multiple questions to Gemini."""
        # Build prompt with numbered questions
        questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        prompt = f"""{context}

Questions:

{questions_text}"""

        return await self.complete(model_id, prompt, max_tokens, temperature)
