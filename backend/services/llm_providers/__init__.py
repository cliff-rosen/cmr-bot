"""
LLM Providers Package

Provides a unified interface for multiple LLM providers (Anthropic, OpenAI, Google).

Usage:
    from services.llm_providers import get_provider, get_available_models, Provider

    # Get a provider instance
    provider = get_provider(Provider.ANTHROPIC)

    # Check if configured
    if provider.is_configured():
        response = await provider.complete_multi_question(
            model_id="claude-sonnet-4-20250514",
            context="...",
            questions=["Q1?", "Q2?"]
        )

    # Get all available models with configuration status
    models = get_available_models()
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

from .models import (
    Provider,
    ModelConfig,
    MODELS,
    get_model,
    get_all_models,
    get_models_by_provider,
    get_provider_for_model
)
from .base import LLMProvider, LLMResponse
from .anthropic import AnthropicProvider
from .openai_provider import OpenAIProvider
from .google import GoogleProvider


# Provider instances (singletons)
_providers: Dict[Provider, LLMProvider] = {
    Provider.ANTHROPIC: AnthropicProvider(),
    Provider.OPENAI: OpenAIProvider(),
    Provider.GOOGLE: GoogleProvider(),
}


def get_provider(provider: Provider) -> LLMProvider:
    """Get a provider instance by provider enum."""
    return _providers[provider]


def get_provider_for_model_id(model_id: str) -> Optional[LLMProvider]:
    """Get the provider instance for a given model ID."""
    provider_enum = get_provider_for_model(model_id)
    if provider_enum:
        return _providers.get(provider_enum)
    return None


@dataclass
class ModelInfo:
    """Model information including configuration status."""
    id: str
    display_name: str
    provider: str
    is_configured: bool
    is_reasoning: bool
    context_window: int
    notes: Optional[str]


def get_available_models() -> List[ModelInfo]:
    """
    Get all available models with their configuration status.

    Returns models grouped by provider, indicating which ones
    have API keys configured.
    """
    result = []

    for model in get_all_models():
        provider = _providers.get(model.provider)
        is_configured = provider.is_configured() if provider else False

        result.append(ModelInfo(
            id=model.id,
            display_name=model.display_name,
            provider=model.provider.value,
            is_configured=is_configured,
            is_reasoning=model.is_reasoning,
            context_window=model.context_window,
            notes=model.notes
        ))

    return result


def get_configured_providers() -> List[str]:
    """Get list of provider names that have API keys configured."""
    return [
        provider.name
        for provider in _providers.values()
        if provider.is_configured()
    ]


__all__ = [
    # Provider access
    'get_provider',
    'get_provider_for_model_id',
    'get_available_models',
    'get_configured_providers',

    # Types
    'Provider',
    'ModelConfig',
    'ModelInfo',
    'LLMProvider',
    'LLMResponse',

    # Model registry
    'get_model',
    'get_all_models',
    'get_models_by_provider',
]
