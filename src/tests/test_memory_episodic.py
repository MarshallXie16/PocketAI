"""Episodic-memory tests (src/ai/memory.py): composite recall scoring, the
retrospective JSON gate, and structured key-fact / tone-note extraction.

``_embed`` is patched to deterministic vectors (no OpenAI client) and the
retrospective LLM is patched via ``registry.get_provider``.
"""

import datetime

import numpy as np
import pytest

from src.ai import memory
from src.models.conversation_state import ConversationState
from src.models.memory_entry import MemoryEntry
from src.models.relationship import KeyFact, RelationshipState
from src.providers.base import LLMResult

# 'a', 'b' share an identical embedding so cosine similarity to the query is
# equal — letting the composite modulators (importance/reinforcement/recency)
# decide the ranking in isolation.
_VECTORS = {'a': [1.0, 0.0], 'b': [1.0, 0.0], 'q': [1.0, 0.0]}


def _fake_embed(text):
    return np.asarray(_VECTORS.get(text, [0.0, 0.0]), dtype=np.float32).tobytes()


@pytest.fixture
def patched_embed(monkeypatch):
    monkeypatch.setattr(memory, '_embed', _fake_embed)


@pytest.fixture
def user_ai(make_user, make_ai):
    user = make_user(username='epi_user')
    ai = make_ai(owner=user, name='EpiAI')
    return user.id, ai.id


def _row(content):
    return MemoryEntry.query.filter_by(content=content).first()


class _FakeProvider:
    def __init__(self, text):
        self._text = text

    def generate(self, *, model, system, messages, max_tokens=2048, **kw):
        return LLMResult(text=self._text)


def _patch_provider(monkeypatch, text):
    import src.providers.registry as registry
    monkeypatch.setattr(registry, 'get_provider', lambda model: _FakeProvider(text))


# --- composite scoring --------------------------------------------------------

def test_higher_importance_ranks_first(db, patched_embed, user_ai):
    user_id, ai_id = user_ai
    memory.save_memory(user_id, ai_id, 'a', importance=0.9)
    memory.save_memory(user_id, ai_id, 'b', importance=0.1)

    results = memory.search_memory(user_id, ai_id, 'q', top_k=1)
    assert results == ['a']


def test_higher_access_count_ranks_first(db, patched_embed, user_ai):
    user_id, ai_id = user_ai
    memory.save_memory(user_id, ai_id, 'a', importance=0.5)
    memory.save_memory(user_id, ai_id, 'b', importance=0.5)
    _row('a').access_count = 50
    db.session.commit()

    results = memory.search_memory(user_id, ai_id, 'q', top_k=1)
    assert results == ['a']


def test_recently_accessed_ranks_above_stale(db, patched_embed, user_ai):
    user_id, ai_id = user_ai
    memory.save_memory(user_id, ai_id, 'a', importance=0.5)
    memory.save_memory(user_id, ai_id, 'b', importance=0.5)
    now = datetime.datetime.now(datetime.UTC)
    _row('a').last_accessed = now
    _row('b').last_accessed = now - datetime.timedelta(days=100)
    db.session.commit()

    results = memory.search_memory(user_id, ai_id, 'q', top_k=1)
    assert results == ['a']


# --- retrospective JSON parsing ----------------------------------------------

def test_retrospective_parses_markdown_fenced_json(db, patched_embed, user_ai, monkeypatch):
    user_id, ai_id = user_ai
    _patch_provider(monkeypatch, (
        '```json\n'
        '{"important": true, "situation": "Sam started a new job.",'
        ' "emotional_tone": "proud", "key_insight": "Sam values growth",'
        ' "importance": 0.8, "entity_tags": ["job"], "key_facts": [], "tone_note": null}\n'
        '```'))

    memory.consolidate_and_save(user_id, ai_id, ['line'], 'EpiAI', 'Sam')

    rows = MemoryEntry.query.filter_by(user_id=user_id, ai_id=ai_id).all()
    assert len(rows) == 1
    assert 'Sam started a new job.' in rows[0].content
    assert rows[0].importance == 0.8


def test_unparseable_json_saves_nothing_but_consumes_queue(db, patched_embed, user_ai, monkeypatch):
    user_id, ai_id = user_ai
    state = ConversationState.get_or_create(user_id, ai_id)
    state.memory_queue = ['line1', 'line2']
    state.memory_queue_count = 2
    db.session.commit()
    _patch_provider(monkeypatch, 'this is not json at all')

    memory.consolidate_and_save(user_id, ai_id, ['line1'], 'EpiAI', 'Sam')

    assert MemoryEntry.query.filter_by(user_id=user_id, ai_id=ai_id).count() == 0
    refreshed = ConversationState.query.filter_by(user_id=user_id, ai_id=ai_id).first()
    assert refreshed.memory_queue == ['line2']
    assert refreshed.memory_queue_count == 1


# --- _save_key_facts ----------------------------------------------------------

def test_save_key_facts_validation_dedup_and_bad_due(db, user_ai):
    user_id, ai_id = user_ai
    facts = [
        {'fact_type': 'random', 'content': 'skip me'},            # invalid type -> skipped
        {'fact_type': 'commitment', 'content': 'sleep by 11'},    # valid
        {'fact_type': 'goal', 'content': 'sleep by 11'},          # duplicate content -> deduped
        {'fact_type': 'event', 'content': 'dentist', 'due_at': 'not-a-date'},  # bad due tolerated
    ]
    memory._save_key_facts(user_id, ai_id, facts)

    rows = KeyFact.query.filter_by(user_id=user_id, ai_id=ai_id).all()
    contents = {r.content for r in rows}
    assert contents == {'sleep by 11', 'dentist'}
    assert 'skip me' not in contents
    dentist = next(r for r in rows if r.content == 'dentist')
    assert dentist.due_at is None  # invalid due_at dropped, fact still saved


# --- _save_tone_note ----------------------------------------------------------

def test_tone_note_appended_once_no_duplicate(db, user_ai):
    user_id, ai_id = user_ai
    memory._save_tone_note(user_id, ai_id, 'likes short replies')
    memory._save_tone_note(user_id, ai_id, 'likes short replies')

    state = RelationshipState.query.filter_by(user_id=user_id, ai_id=ai_id).first()
    assert state.tone_prefs == ['likes short replies']


def test_tone_note_capped_at_ten(db, user_ai):
    user_id, ai_id = user_ai
    for i in range(12):
        memory._save_tone_note(user_id, ai_id, f'note{i}')

    state = RelationshipState.query.filter_by(user_id=user_id, ai_id=ai_id).first()
    assert len(state.tone_prefs) == 10
    assert state.tone_prefs == [f'note{i}' for i in range(2, 12)]  # latest 10 kept
