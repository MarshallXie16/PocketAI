import datetime
from src.utils.extensions import db, migrate


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    ai_id = db.Column(db.Integer, db.ForeignKey('ai_model.id', ondelete='CASCADE'), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.datetime.now(datetime.UTC))
    user = db.relationship('User', back_populates='messages')
    ai_model = db.relationship('AIModel', back_populates='messages')

    def __init__(self, user_id, ai_id, sender, message):
        self.user_id = user_id
        self.ai_id = ai_id
        self.sender = sender
        self.message = message
        self.timestamp = datetime.datetime.now(datetime.UTC)