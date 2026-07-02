"""Model → provider routing, alias resolution, and fail-soft cost accounting."""

import logging
import os

from config import DEFAULT_MODEL, MODEL_ALIASES, MODEL_REGISTRY

logger = logging.getLogger(__name__)

_providers = {}
_openai_client = None


def resolve_model(name: str | None) -> str:
    """Map any stored/legacy model name to a canonical registry id.

    Unknown names fall back to DEFAULT_MODEL with a warning — old AIModel rows
    may carry names that predate the registry, and chat must not 500 on them.
    """
    if not name:
        return DEFAULT_MODEL
    name = name.strip()
    if name in MODEL_REGISTRY:
        return name
    if name in MODEL_ALIASES:
        return MODEL_ALIASES[name]
    logger.warning('Unknown model name %r — falling back to %s', name, DEFAULT_MODEL)
    return DEFAULT_MODEL


def get_provider(model_id: str):
    """Return (cached) provider adapter for a canonical model id."""
    provider_name = MODEL_REGISTRY[model_id]['provider']
    if provider_name not in _providers:
        if provider_name == 'anthropic':
            from src.providers.anthropic_provider import AnthropicProvider
            _providers[provider_name] = AnthropicProvider()
        elif provider_name == 'openai':
            from src.providers.openai_provider import OpenAIProvider
            _providers[provider_name] = OpenAIProvider()
        elif provider_name == 'gemini':
            from src.providers.gemini_provider import GeminiProvider
            _providers[provider_name] = GeminiProvider()
        else:
            raise ValueError(f'Unknown provider: {provider_name}')
    return _providers[provider_name]


def get_openai_client():
    """Shared OpenAI client for non-chat APIs (embeddings, transcription)."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    return _openai_client


def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float | None:
    """Approximate call cost in USD; None (never a raise) for unknown models."""
    entry = MODEL_REGISTRY.get(model_id)
    if not entry:
        logger.warning('No pricing for model %r', model_id)
        return None
    return (input_tokens * entry['input'] + output_tokens * entry['output']) / 1_000_000
