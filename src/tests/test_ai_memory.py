"""Tests for long-term memory (src/ai/memory.py).

``_embed`` is patched to return deterministic one-hot-ish float32 vectors so
cosine ranking is exact and no OpenAI client is constructed. Runs inside the
app context (in-memory SQLite) via the shared fixtures.
"""

import datetime

import numpy as np
import pytest

from src.ai import memory
from src.models.memory_entry import MemoryEntry
from src.providers.base import LLMResult


# vectors chosen so the query overlaps all three rows with a strict ordering:
# cosine(query, first) > (query, second) > (query, third).
_VECTORS = {
    'first': [1.0, 0.0, 0.0],
    'second': [0.0, 1.0, 0.0],
    'third': [0.0, 0.0, 1.0],
    'query': [3.0, 2.0, 1.0],
}


def _fake_embed(text):
    vec = _VECTORS.get(text, [0.0, 0.0, 0.0])
    return np.asarray(vec, dtype=np.float32).tobytes()


@pytest.fixture
def patched_embed(monkeypatch):
    monkeypatch.setattr(memory, '_embed', _fake_embed)


@pytest.fixture
def user_ai(make_user, make_ai):
    user = make_user(username='mem_user')
    ai = make_ai(owner=user, name='MemAI')
    return user.id, ai.id


# --- save_memory --------------------------------------------------------------

def test_save_memory_writes_row_with_embedding_bytes(db, patched_embed, user_ai):
    user_id, ai_id = user_ai
    entry = memory.save_memory(user_id, ai_id, 'first')

    row = MemoryEntry.query.get(entry.id)
    assert row is not None
    assert row.content == 'first'
    assert row.embedding == _fake_embed('first')
    # round-trips to the intended vector
    assert np.frombuffer(row.embedding, dtype=np.float32).tolist() == [1.0, 0.0, 0.0]


# --- search_memory ------------------------------------------------------------

def test_search_memory_ranks_by_cosine(db, patched_embed, user_ai):
    user_id, ai_id = user_ai
    memory.save_memory(user_id, ai_id, 'third')
    memory.save_memory(user_id, ai_id, 'first')
    memory.save_memory(user_id, ai_id, 'second')

    results = memory.search_memory(user_id, ai_id, 'query')
    assert results == ['first', 'second', 'third']


def test_search_memory_respects_top_k(db, patched_embed, user_ai):
    user_id, ai_id = user_ai
    for c in ('first', 'second', 'third'):
        memory.save_memory(user_id, ai_id, c)

    results = memory.search_memory(user_id, ai_id, 'query', top_k=2)
    assert results == ['first', 'second']


def test_search_memory_empty_when_no_rows(db, patched_embed, user_ai):
    user_id, ai_id = user_ai
    assert memory.search_memory(user_id, ai_id, 'query') == []


def test_search_memory_updates_access_tracking(db, patched_embed, user_ai):
    user_id, ai_id = user_ai
    for c in ('first', 'second', 'third'):
        memory.save_memory(user_id, ai_id, c)

    before = datetime.datetime.now(datetime.UTC)
    memory.search_memory(user_id, ai_id, 'query', top_k=2)

    rows = {r.content: r for r in MemoryEntry.query.filter_by(user_id=user_id, ai_id=ai_id).all()}
    # the two returned rows were touched
    assert rows['first'].access_count == 1
    assert rows['second'].access_count == 1
    assert rows['first'].last_accessed.replace(tzinfo=datetime.UTC) >= before.replace(microsecond=0)
    # the untouched row keeps its default count
    assert rows['third'].access_count == 0


# --- consolidate_and_save -----------------------------------------------------

class _FakeProvider:
    def __init__(self, text):
        self._text = text

    def generate(self, *, model, system, messages, max_tokens=2048, **kw):
        return LLMResult(text=self._text)


def _patch_provider(monkeypatch, text):
    import src.providers.registry as registry
    monkeypatch.setattr(registry, 'get_provider', lambda model: _FakeProvider(text))


def test_consolidate_saves_episode_and_key_facts(db, patched_embed, user_ai, monkeypatch):
    user_id, ai_id = user_ai
    _patch_provider(monkeypatch, (
        '{"important": true,'
        ' "situation": "Sam adopted a golden retriever named Biscuit.",'
        ' "emotional_tone": "excited", "key_insight": "Sam loves dogs",'
        ' "importance": 0.7, "entity_tags": ["Biscuit", "dogs"],'
        ' "key_facts": [{"fact_type": "event", "content": "vet appointment for Biscuit",'
        ' "due_at": "2026-07-10T17:00:00+00:00"}],'
        ' "tone_note": null}'))

    memory.consolidate_and_save(user_id, ai_id, ['"sam": hi', 'MemAI: hey'], 'MemAI', 'sam')

    rows = MemoryEntry.query.filter_by(user_id=user_id, ai_id=ai_id).all()
    assert len(rows) == 1
    assert 'Sam adopted a golden retriever named Biscuit.' in rows[0].content
    assert rows[0].content[:4].isdigit()  # leading date stamp
    assert rows[0].importance == 0.7
    assert rows[0].key_insight == 'Sam loves dogs'

    from src.models.relationship import KeyFact
    facts = KeyFact.query.filter_by(user_id=user_id, ai_id=ai_id).all()
    assert len(facts) == 1
    assert facts[0].fact_type == 'event'
    assert facts[0].due_at is not None


def test_consolidate_false_saves_nothing(db, patched_embed, user_ai, monkeypatch):
    user_id, ai_id = user_ai
    _patch_provider(monkeypatch, '{"important": false}')

    memory.consolidate_and_save(user_id, ai_id, ['"sam": weather?', 'MemAI: sunny'], 'MemAI', 'sam')

    assert MemoryEntry.query.filter_by(user_id=user_id, ai_id=ai_id).count() == 0


def test_consolidate_empty_text_saves_nothing(db, patched_embed, user_ai, monkeypatch):
    user_id, ai_id = user_ai
    _patch_provider(monkeypatch, '   ')

    memory.consolidate_and_save(user_id, ai_id, ['x'], 'MemAI', 'sam')

    assert MemoryEntry.query.filter_by(user_id=user_id, ai_id=ai_id).count() == 0
