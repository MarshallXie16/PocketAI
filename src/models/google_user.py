"""Google OAuth credential model.

Defines GoogleUser, which stores a user's Google access/refresh tokens
(Fernet-encrypted at rest via EncryptedString) for the calendar and email
integrations, keyed one-to-one to a User by google_id.
"""

from flask_login import UserMixin

from src.utils.crypto import EncryptedString
from src.extensions import db


class GoogleUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(256), db.ForeignKey('user.google_id', ondelete='CASCADE'), nullable=False, unique=True)
    # Tokens are encrypted at rest (Fernet) — see src/utils/crypto.py.
    access_token = db.Column(EncryptedString, nullable=True)
    refresh_token = db.Column(EncryptedString, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, google_id):
        self.google_id = google_id
