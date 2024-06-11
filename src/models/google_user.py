from flask_login import UserMixin
from src.utils.extensions import db, migrate


class GoogleUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(128), db.ForeignKey('user.google_id'))
    access_token = db.Column(db.String(512), nullable=True)
    refresh_token = db.Column(db.String(512), nullable=True)
    token_expire_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, google_id):
        self.google_id = google_id
