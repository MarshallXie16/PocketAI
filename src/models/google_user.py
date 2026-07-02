from flask_login import UserMixin

from src.utils.crypto import EncryptedString
from src.utils.extensions import db


class GoogleUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(256), db.ForeignKey('user.google_id', ondelete='CASCADE'), nullable=False, unique=True)
    # Tokens are encrypted at rest (Fernet) — see src/utils/crypto.py.
    access_token = db.Column(EncryptedString, nullable=True)
    refresh_token = db.Column(EncryptedString, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, google_id):
        self.google_id = google_id
