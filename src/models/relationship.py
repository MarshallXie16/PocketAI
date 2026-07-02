import datetime

from src.extensions import db


def _now():
    return datetime.datetime.now(datetime.UTC)


class RelationshipState(db.Model):
    """Continuity of one user–companion relationship.

    Powers the relationship block in the system prompt ("you've talked for
    12 days...") and, later, proactive triggers. Deliberately no guilt
    mechanics — streaks inform tone, they are never surfaced as pressure.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    ai_id = db.Column(db.Integer, db.ForeignKey('ai_model.id', ondelete='CASCADE'), nullable=False)
    first_met_at = db.Column(db.DateTime, default=_now)
    last_interaction_at = db.Column(db.DateTime, default=_now)
    streak_days = db.Column(db.Integer, default=0, nullable=False)
    longest_streak = db.Column(db.Integer, default=0, nullable=False)
    total_interactions = db.Column(db.Integer, default=0, nullable=False)
    tone_prefs = db.Column(db.JSON, default=list)   # learned style notes, e.g. "prefers gentle nudges"

    __table_args__ = (db.UniqueConstraint('user_id', 'ai_id', name='uq_relationship_user_ai'),)

    @classmethod
    def get_or_create(cls, user_id, ai_id):
        from sqlalchemy.exc import IntegrityError

        state = cls.query.filter_by(user_id=user_id, ai_id=ai_id).first()
        if state is None:
            state = cls(user_id=user_id, ai_id=ai_id)
            db.session.add(state)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                state = cls.query.filter_by(user_id=user_id, ai_id=ai_id).first()
        return state


class KeyFact(db.Model):
    """Structured, actionable memory — the half vector search can't do.

    Vector memory answers "what do I remember about X?"; key facts answer
    "what is due tomorrow?" / "whose birthday is today?". Commitments with a
    due_at drive proactive follow-through (Phase 4b).
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    ai_id = db.Column(db.Integer, db.ForeignKey('ai_model.id', ondelete='CASCADE'), nullable=False)
    fact_type = db.Column(db.String(32), nullable=False)   # commitment | event | person | preference | goal
    content = db.Column(db.Text, nullable=False)
    due_at = db.Column(db.DateTime, nullable=True)          # commitments/events -> proactive follow-up
    resolved = db.Column(db.Boolean, default=False, nullable=False)
    source = db.Column(db.String(32), default='retrospective')  # retrospective | tool | user
    created_at = db.Column(db.DateTime, default=_now)

    __table_args__ = (db.Index('ix_key_fact_user_ai_due', 'user_id', 'ai_id', 'due_at'),)


class ScheduledMessage(db.Model):
    """A proactive message the agent (or a default schedule) planned to send.

    Content is generated AT DELIVERY TIME with fresh context — this row only
    records the intent and trigger context. Delivered via the proactive tick
    (Phase 4b) as an in-app Message(initiated=True).
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    ai_id = db.Column(db.Integer, db.ForeignKey('ai_model.id', ondelete='CASCADE'), nullable=False)
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    trigger = db.Column(db.String(32), nullable=False)      # daily_checkin | commitment | event | planner
    trigger_context = db.Column(db.Text, default='')         # why this exists, fed to the initiate prompt
    status = db.Column(db.String(16), default='pending', nullable=False, index=True)
    # pending | sent | skipped (SKIP gate) | cancelled | failed
    created_at = db.Column(db.DateTime, default=_now)
    delivered_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
