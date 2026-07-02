"""Relationship continuity: streaks, tone, and the facts that matter.

Feeds a compact block into the companion's system prompt each turn, and
records interaction continuity after each turn. Deliberately subtle — the
data informs tone and follow-through, never guilt mechanics.
"""

import datetime
import logging

from src.extensions import db
from src.models.relationship import KeyFact, RelationshipState

logger = logging.getLogger(__name__)


def _now():
    return datetime.datetime.now(datetime.UTC)


def record_interaction(user_id: int, ai_id: int) -> None:
    """Bump continuity counters after a chat turn."""
    state = RelationshipState.get_or_create(user_id, ai_id)
    now = _now()
    last = state.last_interaction_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=datetime.UTC)

    if last is None:
        state.streak_days = 1
    else:
        gap_days = (now.date() - last.date()).days
        if gap_days == 1:
            state.streak_days = (state.streak_days or 0) + 1
        elif gap_days > 1:
            state.streak_days = 1
        # same-day interactions leave the streak unchanged

    state.longest_streak = max(state.longest_streak or 0, state.streak_days or 0)
    state.total_interactions = (state.total_interactions or 0) + 1
    state.last_interaction_at = now
    db.session.commit()


def context_block(user_id: int, ai_id: int, username: str) -> str:
    """Render the relationship context injected into the system prompt."""
    state = RelationshipState.query.filter_by(user_id=user_id, ai_id=ai_id).first()
    if state is None or not state.total_interactions:
        return ''

    days_known = max((_now().date() - state.first_met_at.date()).days, 0) if state.first_met_at else 0
    parts = [
        f'Relationship context: you have known {username} for {days_known} days '
        f'({state.total_interactions} conversations).'
    ]
    if state.tone_prefs:
        parts.append('What you know about how they like to talk: ' + '; '.join(state.tone_prefs[-5:]))

    upcoming = (KeyFact.query
                .filter(KeyFact.user_id == user_id, KeyFact.ai_id == ai_id,
                        KeyFact.resolved.is_(False))
                .order_by(KeyFact.due_at.isnot(None).desc(), KeyFact.due_at)
                .limit(6).all())
    if upcoming:
        lines = []
        for fact in upcoming:
            due = f" (due {fact.due_at.strftime('%Y-%m-%d %H:%M')} UTC)" if fact.due_at else ''
            lines.append(f'- [{fact.fact_type}] {fact.content}{due}')
        parts.append('Things that currently matter to them:\n' + '\n'.join(lines))

    parts.append('Use this naturally — reference it when relevant, never recite it.')
    return '\n'.join(parts)
