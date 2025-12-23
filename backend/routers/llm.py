from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from services.llm import (
    get_models_by_provider,
    Provider,
    ModelFamily,
)

router = APIRouter(prefix="/llm", tags=["llm"])


def _model_to_dict(model) -> Dict[str, Any]:
    """Convert a ModelConfig to a dict for API response."""
    return {
        "id": model.id,
        "display_name": model.display_name,
        "description": model.description,
        "context_window": model.context_window,
        "max_output_tokens": model.max_output_tokens,
        "family": model.family.value,
        "is_reasoning": model.is_reasoning,
        "supports_temperature": model.supports_temperature,
        "uses_max_completion_tokens": model.uses_max_completion_tokens,
        "aliases": model.aliases,
        "features": model.features,
        "training_data_cutoff": model.training_data_cutoff,
    }


@router.get("/models")
async def get_models() -> Dict[str, Any]:
    """
    Get all available models and their configurations.
    Returns model data organized by provider.
    """
    try:
        openai_models = get_models_by_provider(Provider.OPENAI)
        anthropic_models = get_models_by_provider(Provider.ANTHROPIC)
        google_models = get_models_by_provider(Provider.GOOGLE)

        return {
            "openai": {
                "models": {m.id: _model_to_dict(m) for m in openai_models},
            },
            "anthropic": {
                "models": {m.id: _model_to_dict(m) for m in anthropic_models},
            },
            "google": {
                "models": {m.id: _model_to_dict(m) for m in google_models},
            },
            "families": {f.value: f.value for f in ModelFamily},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
