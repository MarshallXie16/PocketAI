"""Short-term conversation state model.

Defines ConversationState: per-(user, ai) server-side scratch state — the
memory_queue awaiting consolidation, carried-forward past_context, and any
pending_action (a drafted calendar/email tool call awaiting user confirmation).
"""

import datetime

from src.extensions import db


class ConversationState(db.Model):
    """Server-side short-term conversation state per (user, ai) pair.

    Replaces the rolling summary queue that previously lived in the Flask
    session cookie — which was capped by cookie size and desynced across
    workers/devices.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    ai_id = db.Column(db.Integer, db.ForeignKey('ai_model.id', ondelete='CASCADE'), nullable=False)
    memory_queue = db.Column(db.JSON, default=list)     # recent exchange summaries awaiting consolidation
    memory_queue_count = db.Column(db.Integer, default=0)
    past_context = db.Column(db.Text, default='')       # last turn's retrieved context (carried forward)
    # Pending consequential action (calendar_create/email_send draft) awaiting
    # user confirmation: {'tool', 'args', 'message_id'} — message_id is the
    # newest Message at draft time; confirmation requires a LATER user message.
    pending_action = db.Column(db.JSON, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    __table_args__ = (db.UniqueConstraint('user_id', 'ai_id', name='uq_conversation_state_user_ai'),)

    @classmethod
    def get_or_create(cls, user_id, ai_id):
        """Fetch (with a row lock where the backend supports it) or create.

        Concurrent first-turns can race on the unique constraint — the loser
        retries the fetch. Queue updates are last-write-wins by design
        (double-sends from one user are rare and low-stakes).
        """
        from sqlalchemy.exc import IntegrityError

        state = cls.query.filter_by(user_id=user_id, ai_id=ai_id).with_for_update().first()
        if state is None:
            state = cls(user_id=user_id, ai_id=ai_id)
            state.memory_queue = []
            state.memory_queue_count = 0
            db.session.add(state)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                state = cls.query.filter_by(user_id=user_id, ai_id=ai_id).with_for_update().first()
        return state
