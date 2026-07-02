"""Tests for relationship continuity (src/services/relationship_service.py).

record_interaction bumps streak/total counters; context_block renders the
prompt block. No providers involved — pure DB logic under the shared
in-memory-SQLite fixtures.
"""

import datetime

import pytest

from src.extensions import db
from src.models.relationship import KeyFact, RelationshipState
from src.services import relationship_service


@pytest.fixture
def user_ai(make_user, make_ai):
    user = make_user(username='rel_user')
    ai = make_ai(owner=user, name='RelAI')
    return user, ai


def _state(user_id, ai_id):
    return RelationshipState.query.filter_by(user_id=user_id, ai_id=ai_id).first()


def _set_last(user_id, ai_id, dt):
    """Force last_interaction_at to a specific moment (drives the gap math)."""
    state = _state(user_id, ai_id)
    state.last_interaction_at = dt
    db.session.commit()


# BUG: RelationshipState.last_interaction_at has a column default of _now
# (src/models/relationship.py:22) that fires during get_or_create's flush, so
# by the time record_interaction runs (src/services/relationship_service.py:29)
# `last` is never None — the `if last is None: streak_days = 1` branch is dead
# code. A brand-new relationship's first interaction therefore records
# streak_days=0 (and longest_streak=0) instead of 1, and every streak is
# off-by-one until a >1-day gap resets it. These tests assert the intended
# behavior; they xpass once the model default is removed / the branch is fixed.
_FIRST_STREAK_BUG = pytest.mark.xfail(
    reason='last_interaction_at column default makes the first-interaction '
           'streak=1 branch unreachable (streak stays 0)',
    strict=False,
)


# --- record_interaction: streak transitions ----------------------------------

def test_first_interaction_sets_streak_one(db, user_ai):
    user, ai = user_ai
    relationship_service.record_interaction(user.id, ai.id)

    state = _state(user.id, ai.id)
    assert state.streak_days == 1
    assert state.longest_streak == 1
    assert state.total_interactions == 1


def test_next_day_bumps_streak(db, user_ai):
    user, ai = user_ai
    relationship_service.record_interaction(user.id, ai.id)
    _set_last(user.id, ai.id, datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))

    relationship_service.record_interaction(user.id, ai.id)

    state = _state(user.id, ai.id)
    assert state.streak_days == 2
    assert state.total_interactions == 2


def test_same_day_leaves_streak_unchanged(db, user_ai):
    user, ai = user_ai
    relationship_service.record_interaction(user.id, ai.id)  # streak 1
    _set_last(user.id, ai.id, datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))
    relationship_service.record_interaction(user.id, ai.id)  # streak 2

    # a second interaction the *same* day must not bump the streak
    relationship_service.record_interaction(user.id, ai.id)

    state = _state(user.id, ai.id)
    assert state.streak_days == 2
    assert state.total_interactions == 3


def test_gap_over_one_day_resets_streak(db, user_ai):
    user, ai = user_ai
    relationship_service.record_interaction(user.id, ai.id)
    _set_last(user.id, ai.id, datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))
    relationship_service.record_interaction(user.id, ai.id)  # streak 2

    _set_last(user.id, ai.id, datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=3))
    relationship_service.record_interaction(user.id, ai.id)

    state = _state(user.id, ai.id)
    assert state.streak_days == 1


def test_longest_streak_tracks_max(db, user_ai):
    user, ai = user_ai
    relationship_service.record_interaction(user.id, ai.id)
    _set_last(user.id, ai.id, datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))
    relationship_service.record_interaction(user.id, ai.id)  # streak 2, longest 2

    # a >1-day gap resets the current streak but longest_streak holds the peak
    _set_last(user.id, ai.id, datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=5))
    relationship_service.record_interaction(user.id, ai.id)  # streak back to 1

    state = _state(user.id, ai.id)
    assert state.streak_days == 1
    assert state.longest_streak == 2


def test_total_interactions_increments_each_call(db, user_ai):
    user, ai = user_ai
    for _ in range(4):
        relationship_service.record_interaction(user.id, ai.id)
    assert _state(user.id, ai.id).total_interactions == 4


# --- context_block ------------------------------------------------------------

def test_context_block_empty_without_state(db, user_ai):
    user, ai = user_ai
    assert relationship_service.context_block(user.id, ai.id, user.username) == ''


def test_context_block_empty_with_zero_interactions(db, user_ai):
    user, ai = user_ai
    # a state row exists but no interactions recorded -> still empty
    RelationshipState.get_or_create(user.id, ai.id)
    db.session.commit()
    assert relationship_service.context_block(user.id, ai.id, user.username) == ''


def test_context_block_includes_days_known_and_count(db, user_ai):
    user, ai = user_ai
    state = RelationshipState.get_or_create(user.id, ai.id)
    state.total_interactions = 5
    state.first_met_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=10)
    db.session.commit()

    block = relationship_service.context_block(user.id, ai.id, user.username)
    assert f'known {user.username} for 10 days' in block
    assert '(5 conversations)' in block


def test_context_block_includes_unresolved_facts_excludes_resolved(db, user_ai):
    user, ai = user_ai
    state = RelationshipState.get_or_create(user.id, ai.id)
    state.total_interactions = 2
    db.session.commit()

    due = datetime.datetime(2026, 7, 10, 17, 0)
    db.session.add(KeyFact(user_id=user.id, ai_id=ai.id, fact_type='event',
                           content='Amazon interview', due_at=due))
    resolved = KeyFact(user_id=user.id, ai_id=ai.id, fact_type='commitment',
                       content='already handled thing')
    resolved.resolved = True
    db.session.add(resolved)
    db.session.commit()

    block = relationship_service.context_block(user.id, ai.id, user.username)
    assert 'Amazon interview' in block
    assert '2026-07-10 17:00 UTC' in block
    assert 'already handled thing' not in block


def test_context_block_includes_tone_prefs(db, user_ai):
    user, ai = user_ai
    state = RelationshipState.get_or_create(user.id, ai.id)
    state.total_interactions = 3
    state.tone_prefs = ['prefers gentle nudges']
    db.session.commit()

    block = relationship_service.context_block(user.id, ai.id, user.username)
    assert 'prefers gentle nudges' in block
