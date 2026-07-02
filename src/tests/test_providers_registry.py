"""Unit tests for src/providers/registry.py.

Covers model-name resolution (canonical / alias / unknown / empty), fail-soft
cost math, and provider adapter routing + instance caching. No SDKs are
constructed: adapter classes have no SDK imports at construction time (the
SDK client is built lazily inside each module's ``_get_client``).
"""

import logging

import pytest

from config import DEFAULT_MODEL, MODEL_REGISTRY
from src.providers import registry
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.gemini_provider import GeminiProvider
from src.providers.openai_provider import OpenAIProvider


# --- resolve_model ------------------------------------------------------------

def test_resolve_model_canonical_passthrough():
    assert registry.resolve_model('claude-opus-4-8') == 'claude-opus-4-8'
    assert registry.resolve_model('gpt-5.2') == 'gpt-5.2'
    assert registry.resolve_model('gemini-3-flash-preview') == 'gemini-3-flash-preview'


def test_resolve_model_strips_whitespace():
    assert registry.resolve_model('  claude-opus-4-8  ') == 'claude-opus-4-8'


@pytest.mark.parametrize('alias,canonical', [
    ('claude-3-5-sonnet', 'claude-sonnet-4-6'),
    ('claude-3.5-sonnet', 'claude-sonnet-4-6'),
    ('claude-3-haiku', 'claude-haiku-4-5'),
    ('gpt-4o', 'gpt-5.2'),
    ('gpt-4o-mini', 'gpt-5-mini'),
    ('gemini-1.5-pro', 'gemini-3-pro-preview'),
    ('gemini-1.5-flash', 'gemini-3-flash-preview'),
])
def test_resolve_model_alias_mapping(alias, canonical):
    assert registry.resolve_model(alias) == canonical
    # the mapped target must itself be a real registry id
    assert canonical in MODEL_REGISTRY


def test_resolve_model_unknown_falls_back_and_warns(caplog):
    with caplog.at_level(logging.WARNING, logger='src.providers.registry'):
        assert registry.resolve_model('totally-made-up-model') == DEFAULT_MODEL
    assert any('totally-made-up-model' in rec.getMessage() for rec in caplog.records)
    assert any(rec.levelno == logging.WARNING for rec in caplog.records)


@pytest.mark.parametrize('empty', [None, '', '   '])
def test_resolve_model_empty_falls_back(empty):
    # None/'' short-circuit; whitespace-only strips to '' then misses the
    # registry -> DEFAULT_MODEL either way.
    assert registry.resolve_model(empty) == DEFAULT_MODEL


# --- calculate_cost -----------------------------------------------------------

def test_calculate_cost_known_model_math():
    # claude-opus-4-8: $5/MTok input, $25/MTok output.
    cost = registry.calculate_cost('claude-opus-4-8', 1_000_000, 1_000_000)
    assert cost == pytest.approx(30.0)


def test_calculate_cost_partial_tokens():
    # 200k input @ $1/MTok + 100k output @ $5/MTok = 0.2 + 0.5 = 0.7
    cost = registry.calculate_cost('claude-haiku-4-5', 200_000, 100_000)
    assert cost == pytest.approx(0.7)


def test_calculate_cost_zero_tokens():
    assert registry.calculate_cost('gpt-5.2', 0, 0) == 0.0


def test_calculate_cost_unknown_returns_none_not_raise(caplog):
    with caplog.at_level(logging.WARNING, logger='src.providers.registry'):
        assert registry.calculate_cost('no-such-model', 10, 10) is None
    assert any('no-such-model' in rec.getMessage() for rec in caplog.records)


# --- get_provider (routing + caching) ----------------------------------------

@pytest.fixture
def clean_provider_cache():
    """Isolate the module-level adapter cache for a deterministic test."""
    saved = dict(registry._providers)
    registry._providers.clear()
    try:
        yield
    finally:
        registry._providers.clear()
        registry._providers.update(saved)


def test_get_provider_routes_to_correct_class(clean_provider_cache):
    assert isinstance(registry.get_provider('claude-opus-4-8'), AnthropicProvider)
    assert isinstance(registry.get_provider('gpt-5.2'), OpenAIProvider)
    assert isinstance(registry.get_provider('gemini-3-flash-preview'), GeminiProvider)


def test_get_provider_caches_instances(clean_provider_cache):
    first = registry.get_provider('claude-opus-4-8')
    second = registry.get_provider('claude-haiku-4-5')  # same provider, diff model
    # both anthropic -> exact same cached instance
    assert first is second
    assert isinstance(registry.get_provider('gpt-5.2'), OpenAIProvider)
    # cache holds one instance per provider name, not per model
    assert set(registry._providers) == {'anthropic', 'openai'}
