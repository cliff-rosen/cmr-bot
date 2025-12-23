"""
LLM Model Registry

Central registry of all available LLM models. To add a new model,
simply add an entry to the MODELS dict below.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""
    id: str                          # Internal ID used in API calls
    display_name: str                # Human-readable name
    provider: Provider               # Which provider
    api_model_id: str                # Actual model ID sent to provider API
    is_reasoning: bool = False       # Reasoning models (o1, o3) behave differently
    context_window: int = 128000     # Max context tokens
    max_output_tokens: int = 4096    # Max output tokens
    supports_streaming: bool = True  # Whether model supports streaming
    notes: Optional[str] = None      # Optional notes about the model

    # Parameter support flags (varies by model/provider)
    supports_temperature: bool = True           # Most models support this
    uses_max_completion_tokens: bool = False    # OpenAI newer models use this instead of max_tokens
    supports_reasoning_effort: bool = False     # o3 models support reasoning_effort parameter
    default_reasoning_effort: Optional[str] = None  # "low", "medium", "high" for o3


# =============================================================================
# MODEL REGISTRY
# Add new models here - that's all you need to do!
# =============================================================================

MODELS: Dict[str, ModelConfig] = {
    # -------------------------------------------------------------------------
    # ANTHROPIC
    # -------------------------------------------------------------------------
    "claude-opus-4.5": ModelConfig(
        id="claude-opus-4.5",
        display_name="Claude Opus 4.5",
        provider=Provider.ANTHROPIC,
        api_model_id="claude-opus-4-5-20251101",
        context_window=200000,
        max_output_tokens=8192,
        notes="Most capable Anthropic model"
    ),
    "claude-sonnet-4.5": ModelConfig(
        id="claude-sonnet-4.5",
        display_name="Claude Sonnet 4.5",
        provider=Provider.ANTHROPIC,
        api_model_id="claude-sonnet-4-5-20250929",
        context_window=1000000,  # 1M with beta header
        max_output_tokens=8192,
        notes="Balanced performance, supports 1M context"
    ),
    "claude-sonnet-4": ModelConfig(
        id="claude-sonnet-4",
        display_name="Claude Sonnet 4",
        provider=Provider.ANTHROPIC,
        api_model_id="claude-sonnet-4-20250514",
        context_window=200000,
        max_output_tokens=8192,
        notes="Previous generation Sonnet"
    ),
    "claude-haiku-3.5": ModelConfig(
        id="claude-haiku-3.5",
        display_name="Claude Haiku 3.5",
        provider=Provider.ANTHROPIC,
        api_model_id="claude-3-5-haiku-20241022",
        context_window=200000,
        max_output_tokens=8192,
        notes="Fast and cost-effective"
    ),

    # -------------------------------------------------------------------------
    # OPENAI
    # Note: GPT-4.1+ and GPT-5+ use max_completion_tokens, not max_tokens
    # Reasoning models (o3) don't support temperature
    # -------------------------------------------------------------------------
    "gpt-5.2": ModelConfig(
        id="gpt-5.2",
        display_name="GPT-5.2",
        provider=Provider.OPENAI,
        api_model_id="gpt-5.2",
        context_window=256000,
        max_output_tokens=16384,
        uses_max_completion_tokens=True,
        notes="Current OpenAI flagship"
    ),
    "gpt-5.1": ModelConfig(
        id="gpt-5.1",
        display_name="GPT-5.1",
        provider=Provider.OPENAI,
        api_model_id="gpt-5.1",
        context_window=256000,
        max_output_tokens=16384,
        uses_max_completion_tokens=True,
        notes="Previous flagship"
    ),
    "gpt-5-mini": ModelConfig(
        id="gpt-5-mini",
        display_name="GPT-5 Mini",
        provider=Provider.OPENAI,
        api_model_id="gpt-5-mini",
        context_window=128000,
        max_output_tokens=8192,
        uses_max_completion_tokens=True,
        notes="Balanced GPT-5 variant"
    ),
    "gpt-4.1": ModelConfig(
        id="gpt-4.1",
        display_name="GPT-4.1",
        provider=Provider.OPENAI,
        api_model_id="gpt-4.1",
        context_window=128000,
        max_output_tokens=8192,
        uses_max_completion_tokens=True,
        notes="Stable workhorse"
    ),
    "gpt-4.1-mini": ModelConfig(
        id="gpt-4.1-mini",
        display_name="GPT-4.1 Mini",
        provider=Provider.OPENAI,
        api_model_id="gpt-4.1-mini",
        context_window=128000,
        max_output_tokens=8192,
        uses_max_completion_tokens=True,
        notes="Fast and cheap"
    ),
    "o3": ModelConfig(
        id="o3",
        display_name="o3",
        provider=Provider.OPENAI,
        api_model_id="o3",
        is_reasoning=True,
        context_window=200000,
        max_output_tokens=100000,
        supports_streaming=False,
        supports_temperature=False,
        uses_max_completion_tokens=True,
        supports_reasoning_effort=True,
        default_reasoning_effort="medium",
        notes="Reasoning model - higher latency"
    ),
    "o3-mini": ModelConfig(
        id="o3-mini",
        display_name="o3 Mini",
        provider=Provider.OPENAI,
        api_model_id="o3-mini",
        is_reasoning=True,
        context_window=200000,
        max_output_tokens=65536,
        supports_streaming=False,
        supports_temperature=False,
        uses_max_completion_tokens=True,
        supports_reasoning_effort=True,
        default_reasoning_effort="medium",
        notes="Faster reasoning model"
    ),

    # -------------------------------------------------------------------------
    # GOOGLE
    # -------------------------------------------------------------------------
    "gemini-3-pro": ModelConfig(
        id="gemini-3-pro",
        display_name="Gemini 3 Pro",
        provider=Provider.GOOGLE,
        api_model_id="gemini-3-pro-preview",
        context_window=200000,
        max_output_tokens=8192,
        notes="Latest Google reasoning model"
    ),
    "gemini-3-flash": ModelConfig(
        id="gemini-3-flash",
        display_name="Gemini 3 Flash",
        provider=Provider.GOOGLE,
        api_model_id="gemini-3-flash-preview",
        context_window=200000,
        max_output_tokens=8192,
        notes="Latest fast model"
    ),
    "gemini-2.5-pro": ModelConfig(
        id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider=Provider.GOOGLE,
        api_model_id="gemini-2.5-pro",
        context_window=1000000,
        max_output_tokens=8192,
        notes="1M context window"
    ),
    "gemini-2.5-flash": ModelConfig(
        id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        provider=Provider.GOOGLE,
        api_model_id="gemini-2.5-flash",
        context_window=1000000,
        max_output_tokens=8192,
        notes="Best price/performance"
    ),
    "gemini-2.0-flash": ModelConfig(
        id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        provider=Provider.GOOGLE,
        api_model_id="gemini-2.0-flash",
        context_window=1000000,
        max_output_tokens=8192,
        notes="Stable multimodal model"
    ),
}


def get_model(model_id: str) -> Optional[ModelConfig]:
    """Get a model config by ID."""
    return MODELS.get(model_id)


def get_all_models() -> List[ModelConfig]:
    """Get all registered models."""
    return list(MODELS.values())


def get_models_by_provider(provider: Provider) -> List[ModelConfig]:
    """Get all models for a specific provider."""
    return [m for m in MODELS.values() if m.provider == provider]


def get_provider_for_model(model_id: str) -> Optional[Provider]:
    """Get the provider for a model ID."""
    model = MODELS.get(model_id)
    return model.provider if model else None
