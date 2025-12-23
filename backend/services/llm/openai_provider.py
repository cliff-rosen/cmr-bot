from openai import AsyncOpenAI
import logging
from typing import List, Dict, Optional, AsyncGenerator, Any, Set
from config.settings import settings
from .base import LLMProvider
from .models import get_model, MODEL_ALIASES, ModelConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI models with typed model configuration."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    def get_default_model(self) -> str:
        return "gpt-5.2"

    def _resolve_model(self, model_id: str) -> tuple[str, Optional[ModelConfig]]:
        """
        Resolve model ID (handling aliases) and get config.

        Returns:
            Tuple of (resolved_model_id, ModelConfig or None)
        """
        # Check if it's an alias
        resolved_id = MODEL_ALIASES.get(model_id, model_id)
        config = get_model(resolved_id)
        return resolved_id, config

    def _build_params(
        self,
        model: str,
        config: Optional[ModelConfig],
        messages: Optional[List[Dict[str, str]]] = None,
        prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Build API parameters based on model configuration.

        Uses typed ModelConfig flags for clean parameter handling.
        """
        params: Dict[str, Any] = {"model": model}

        # Messages or prompt
        if messages is not None:
            params["messages"] = messages
        elif prompt is not None:
            params["prompt"] = prompt

        # Max tokens - reasoning models use max_completion_tokens
        if max_tokens is not None:
            if config and config.uses_max_completion_tokens:
                params["max_completion_tokens"] = max_tokens
            else:
                params["max_tokens"] = max_tokens

        # Temperature - some models don't support it or only support default
        if temperature is not None:
            if config and not config.supports_temperature:
                if temperature != 1.0:
                    logger.warning(
                        f"Model {model} doesn't support temperature={temperature}, ignoring"
                    )
                # Don't set temperature at all for models that don't support it
            else:
                params["temperature"] = temperature

        if stream:
            params["stream"] = True

        return params

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate using chat completions API (all modern OpenAI models are chat models)."""
        try:
            model = model or self.get_default_model()
            resolved_model, config = self._resolve_model(model)

            messages = [{"role": "user", "content": prompt}]
            params = self._build_params(
                model=resolved_model,
                config=config,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating OpenAI response with model {model}: {str(e)}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        """Stream using chat completions API."""
        try:
            model = model or self.get_default_model()
            resolved_model, config = self._resolve_model(model)

            messages = [{"role": "user", "content": prompt}]
            params = self._build_params(
                model=resolved_model,
                config=config,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )

            stream = await self.client.chat.completions.create(**params)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error generating streaming OpenAI response with model {model}: {str(e)}")
            raise

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
            model = model or self.get_default_model()
            resolved_model, config = self._resolve_model(model)

            # Add system message if provided
            chat_messages = []
            if system:
                chat_messages.append({"role": "system", "content": system})
            chat_messages.extend(messages)

            params = self._build_params(
                model=resolved_model,
                config=config,
                messages=chat_messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error creating OpenAI chat completion with model {model}: {str(e)}")
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
        try:
            model = model or self.get_default_model()
            resolved_model, config = self._resolve_model(model)

            # Add system message if provided
            chat_messages = []
            if system:
                chat_messages.append({"role": "system", "content": system})
            chat_messages.extend(messages)

            params = self._build_params(
                model=resolved_model,
                config=config,
                messages=chat_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )

            stream = await self.client.chat.completions.create(**params)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error creating streaming OpenAI chat completion with model {model}: {str(e)}")
            raise

    async def close(self):
        await self.client.close()
