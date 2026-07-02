import datetime

from src.utils.extensions import db


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
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    __table_args__ = (db.UniqueConstraint('user_id', 'ai_id', name='uq_conversation_state_user_ai'),)

    @classmethod
    def get_or_create(cls, user_id, ai_id):
        state = cls.query.filter_by(user_id=user_id, ai_id=ai_id).first()
        if state is None:
            state = cls(user_id=user_id, ai_id=ai_id)
            state.memory_queue = []
            state.memory_queue_count = 0
            db.session.add(state)
        return state
