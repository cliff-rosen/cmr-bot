"""
LLM Services Package

Provides a unified interface for multiple LLM providers (Anthropic, OpenAI, Google).

Usage:
    from services.llm import get_provider, get_available_models

    # Get a provider instance
    provider = get_provider("anthropic")

    # Check if configured
    if provider:
        response = await provider.complete_multi_question(
            model_id="claude-sonnet-4-20250514",
            context="...",
            questions=["Q1?", "Q2?"]
        )

    # Get all available models for testing UI
    models = get_available_models()
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

from config.settings import settings
from .base import LLMProvider, LLMTestResponse
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider
from .models import (
    Provider,
    ModelFamily,
    ModelConfig,
    MODELS,
    MODEL_ALIASES,
    DEFAULT_MODELS,
    FAST_MODELS,
    get_model,
    get_all_models as _get_all_model_configs,
    get_models_by_provider,
    get_provider_for_model,
    get_reasoning_models,
    get_models_by_family,
)


@dataclass
class ModelInfo:
    """Model information for the testing UI."""
    id: str
    display_name: str
    provider: str
    is_configured: bool
    is_reasoning: bool
    context_window: int
    notes: Optional[str]


# Provider instances (lazy-loaded singletons)
_providers: Dict[str, Optional[LLMProvider]] = {}


def _is_provider_configured(provider: str) -> bool:
    """Check if a provider has its API key configured."""
    if provider == "anthropic":
        return bool(settings.ANTHROPIC_API_KEY)
    elif provider == "openai":
        return bool(settings.OPENAI_API_KEY)
    elif provider == "google":
        return bool(settings.GOOGLE_AI_API_KEY)
    return False


def get_provider(provider: str) -> Optional[LLMProvider]:
    """
    Get a provider instance by name.
    Returns None if the provider is not configured.
    """
    if provider not in _providers:
        if not _is_provider_configured(provider):
            _providers[provider] = None
        elif provider == "anthropic":
            _providers[provider] = AnthropicProvider()
        elif provider == "openai":
            _providers[provider] = OpenAIProvider()
        elif provider == "google":
            _providers[provider] = GoogleProvider()
        else:
            _providers[provider] = None

    return _providers[provider]


def get_available_models() -> List[ModelInfo]:
    """
    Get all available models with their configuration status.
    Used by the LLM testing UI to show which models can be tested.
    """
    result = []

    for model in _get_all_model_configs():
        provider_name = model.provider.value
        is_configured = _is_provider_configured(provider_name)

        result.append(ModelInfo(
            id=model.id,
            display_name=model.display_name,
            provider=provider_name,
            is_configured=is_configured,
            is_reasoning=model.is_reasoning,
            context_window=model.context_window,
            notes=model.description
        ))

    return result


def get_configured_providers() -> List[str]:
    """Get list of provider names that have API keys configured."""
    providers = []
    if _is_provider_configured("anthropic"):
        providers.append("anthropic")
    if _is_provider_configured("openai"):
        providers.append("openai")
    if _is_provider_configured("google"):
        providers.append("google")
    return providers


def get_model_provider(model_id: str) -> Optional[str]:
    """Get the provider name for a given model ID."""
    provider = get_provider_for_model(model_id)
    return provider.value if provider else None


__all__ = [
    # Provider access
    'get_provider',
    'get_available_models',
    'get_configured_providers',
    'get_model_provider',

    # Types
    'Provider',
    'ModelFamily',
    'ModelConfig',
    'ModelInfo',
    'LLMProvider',
    'LLMTestResponse',

    # Provider classes
    'AnthropicProvider',
    'OpenAIProvider',
    'GoogleProvider',

    # Model registry
    'MODELS',
    'MODEL_ALIASES',
    'DEFAULT_MODELS',
    'FAST_MODELS',

    # Model helpers
    'get_model',
    'get_models_by_provider',
    'get_provider_for_model',
    'get_reasoning_models',
    'get_models_by_family',
]
