"""
Typed model configuration for LLM providers.

Provides a strongly-typed ModelConfig dataclass with explicit parameter support flags,
replacing the loose Dict[str, Any] approach.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class Provider(Enum):
    """LLM provider identifiers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class ModelFamily(Enum):
    """Model family categories that determine parameter support."""
    REASONING = "reasoning"          # o-series, thinking models
    FLAGSHIP_CHAT = "flagship_chat"  # Full-featured chat models
    COST_OPTIMIZED = "cost_optimized"  # Fast, cheaper models


@dataclass
class ModelConfig:
    """Configuration for an LLM model with explicit typing."""
    id: str
    display_name: str
    provider: Provider
    description: str

    # Context limits
    context_window: int = 128000
    max_output_tokens: int = 4096

    # Model characteristics
    family: ModelFamily = ModelFamily.FLAGSHIP_CHAT
    is_reasoning: bool = False

    # Parameter support flags
    supports_temperature: bool = True
    uses_max_completion_tokens: bool = False  # OpenAI reasoning models use this instead of max_tokens
    supports_system_message: bool = True

    # Reasoning model specific
    supports_reasoning_effort: bool = False
    default_reasoning_effort: Optional[str] = None

    # Token boost for thinking models (multiplier for max_tokens)
    reasoning_token_boost: int = 1  # 1 = no boost, 20 = 20x boost

    # Aliases for this model
    aliases: List[str] = field(default_factory=list)

    # Additional metadata
    training_data_cutoff: Optional[str] = None
    features: List[str] = field(default_factory=list)


# =============================================================================
# Model Registry
# =============================================================================

MODELS: Dict[str, ModelConfig] = {}


def _register(config: ModelConfig) -> ModelConfig:
    """Register a model configuration."""
    MODELS[config.id] = config
    return config


# -----------------------------------------------------------------------------
# Anthropic Models
# -----------------------------------------------------------------------------

_register(ModelConfig(
    id="claude-4-opus-20250514",
    display_name="Claude 4 Opus",
    provider=Provider.ANTHROPIC,
    description="Best model for complex reasoning and analysis",
    context_window=200000,
    max_output_tokens=32000,
    family=ModelFamily.FLAGSHIP_CHAT,
    is_reasoning=False,
    supports_temperature=True,
    features=["vision", "extended_thinking", "priority_tier"],
    aliases=["claude-4"],
    training_data_cutoff="Mar 2025"
))

_register(ModelConfig(
    id="claude-4-sonnet-20250514",
    display_name="Claude 4 Sonnet",
    provider=Provider.ANTHROPIC,
    description="High-performance model for general chat and analysis",
    context_window=200000,
    max_output_tokens=64000,
    family=ModelFamily.FLAGSHIP_CHAT,
    is_reasoning=False,
    supports_temperature=True,
    features=["vision", "extended_thinking", "priority_tier"],
    aliases=["claude-4-sonnet"],
    training_data_cutoff="Mar 2025"
))

_register(ModelConfig(
    id="claude-3-5-haiku-20241022",
    display_name="Claude 3.5 Haiku",
    provider=Provider.ANTHROPIC,
    description="Fastest and most cost-effective model for quick tasks",
    context_window=200000,
    max_output_tokens=8192,
    family=ModelFamily.COST_OPTIMIZED,
    is_reasoning=False,
    supports_temperature=True,
    features=["vision", "priority_tier"],
    aliases=["claude-3.5-haiku"],
    training_data_cutoff="July 2024"
))

# -----------------------------------------------------------------------------
# OpenAI GPT-5 Models
# -----------------------------------------------------------------------------

_register(ModelConfig(
    id="gpt-5.2",
    display_name="GPT-5.2",
    provider=Provider.OPENAI,
    description="Latest flagship model for coding, reasoning, and agentic tasks",
    context_window=400000,
    max_output_tokens=128000,
    family=ModelFamily.FLAGSHIP_CHAT,
    is_reasoning=True,
    supports_temperature=True,
    features=["vision", "json_mode", "function_calling", "reasoning"],
    training_data_cutoff="Aug 2025"
))

_register(ModelConfig(
    id="gpt-5.1",
    display_name="GPT-5.1",
    provider=Provider.OPENAI,
    description="Previous flagship reasoning model",
    context_window=400000,
    max_output_tokens=128000,
    family=ModelFamily.FLAGSHIP_CHAT,
    is_reasoning=True,
    supports_temperature=True,
    features=["vision", "json_mode", "function_calling", "reasoning"],
    training_data_cutoff="Sep 2025"
))

_register(ModelConfig(
    id="gpt-5",
    display_name="GPT-5",
    provider=Provider.OPENAI,
    description="Base GPT-5 model for coding and reasoning",
    context_window=400000,
    max_output_tokens=128000,
    family=ModelFamily.FLAGSHIP_CHAT,
    is_reasoning=True,
    supports_temperature=True,
    features=["vision", "json_mode", "function_calling", "reasoning"],
    training_data_cutoff="Sep 2024"
))

_register(ModelConfig(
    id="gpt-5-mini",
    display_name="GPT-5 Mini",
    provider=Provider.OPENAI,
    description="Faster, cost-efficient version of GPT-5",
    context_window=400000,
    max_output_tokens=64000,
    family=ModelFamily.COST_OPTIMIZED,
    is_reasoning=True,
    supports_temperature=True,
    features=["vision", "json_mode", "function_calling", "reasoning"],
    training_data_cutoff="Sep 2024"
))

_register(ModelConfig(
    id="gpt-5-nano",
    display_name="GPT-5 Nano",
    provider=Provider.OPENAI,
    description="Fastest, cheapest GPT-5 for summarization and classification",
    context_window=128000,
    max_output_tokens=16000,
    family=ModelFamily.COST_OPTIMIZED,
    is_reasoning=False,
    supports_temperature=True,
    features=["json_mode", "function_calling"],
    training_data_cutoff="Sep 2024"
))

# -----------------------------------------------------------------------------
# Google Gemini Models
# -----------------------------------------------------------------------------

_register(ModelConfig(
    id="gemini-3-pro-preview",
    display_name="Gemini 3 Pro",
    provider=Provider.GOOGLE,
    description="Thinking model - uses tokens for reasoning",
    context_window=200000,
    max_output_tokens=65536,
    family=ModelFamily.REASONING,
    is_reasoning=True,
    supports_temperature=True,
    reasoning_token_boost=20  # Needs 20x tokens for thinking
))

_register(ModelConfig(
    id="gemini-3-flash-preview",
    display_name="Gemini 3 Flash",
    provider=Provider.GOOGLE,
    description="Latest fast model",
    context_window=200000,
    max_output_tokens=8192,
    family=ModelFamily.COST_OPTIMIZED,
    is_reasoning=False,
    supports_temperature=True
))

_register(ModelConfig(
    id="gemini-2.5-pro",
    display_name="Gemini 2.5 Pro",
    provider=Provider.GOOGLE,
    description="Thinking model - 1M context window",
    context_window=1000000,
    max_output_tokens=65536,
    family=ModelFamily.REASONING,
    is_reasoning=True,
    supports_temperature=True,
    reasoning_token_boost=20
))

_register(ModelConfig(
    id="gemini-2.5-flash",
    display_name="Gemini 2.5 Flash",
    provider=Provider.GOOGLE,
    description="Best price/performance",
    context_window=1000000,
    max_output_tokens=8192,
    family=ModelFamily.COST_OPTIMIZED,
    is_reasoning=False,
    supports_temperature=True
))

_register(ModelConfig(
    id="gemini-2.0-flash",
    display_name="Gemini 2.0 Flash",
    provider=Provider.GOOGLE,
    description="Stable fast model",
    context_window=200000,
    max_output_tokens=8192,
    family=ModelFamily.COST_OPTIMIZED,
    is_reasoning=False,
    supports_temperature=True
))


# =============================================================================
# Alias Registry (built from model configs)
# =============================================================================

MODEL_ALIASES: Dict[str, str] = {}
for model in MODELS.values():
    for alias in model.aliases:
        MODEL_ALIASES[alias] = model.id


# =============================================================================
# Helper Functions
# =============================================================================

def get_model(model_id: str) -> Optional[ModelConfig]:
    """
    Get a model configuration by ID or alias.

    Args:
        model_id: The model ID or alias

    Returns:
        ModelConfig if found, None otherwise
    """
    # Direct lookup
    if model_id in MODELS:
        return MODELS[model_id]

    # Alias lookup
    if model_id in MODEL_ALIASES:
        canonical_id = MODEL_ALIASES[model_id]
        return MODELS.get(canonical_id)

    return None


def get_all_models() -> List[ModelConfig]:
    """Get all registered models."""
    return list(MODELS.values())


def get_models_by_provider(provider: Provider) -> List[ModelConfig]:
    """Get all models for a specific provider."""
    return [m for m in MODELS.values() if m.provider == provider]


def get_provider_for_model(model_id: str) -> Optional[Provider]:
    """
    Get the provider for a model ID or alias.

    Args:
        model_id: The model ID or alias

    Returns:
        Provider enum if found, None otherwise
    """
    model = get_model(model_id)
    return model.provider if model else None


def get_reasoning_models() -> List[ModelConfig]:
    """Get all reasoning/thinking models."""
    return [m for m in MODELS.values() if m.is_reasoning]


def get_models_by_family(family: ModelFamily) -> List[ModelConfig]:
    """Get all models of a specific family."""
    return [m for m in MODELS.values() if m.family == family]


# =============================================================================
# Default Models
# =============================================================================

DEFAULT_MODELS: Dict[str, str] = {
    "anthropic": "claude-4-opus-20250514",
    "openai": "gpt-5.2",
    "google": "gemini-2.5-flash"
}

FAST_MODELS: Dict[str, str] = {
    "anthropic": "claude-3-5-haiku-20241022",
    "openai": "gpt-5-nano",
    "google": "gemini-2.0-flash"
}


__all__ = [
    # Enums
    'Provider',
    'ModelFamily',

    # Config class
    'ModelConfig',

    # Registry
    'MODELS',
    'MODEL_ALIASES',

    # Helper functions
    'get_model',
    'get_all_models',
    'get_models_by_provider',
    'get_provider_for_model',
    'get_reasoning_models',
    'get_models_by_family',

    # Defaults
    'DEFAULT_MODELS',
    'FAST_MODELS',
]
