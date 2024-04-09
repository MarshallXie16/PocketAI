from flask_login import UserMixin
from src.utils.extensions import db, migrate
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password_hash = db.Column(db.String(128), nullable=True)
    points = db.Column(db.Integer, default=100)
    messages = db.relationship('Message', backref='user', lazy='dynamic')
    auth_type = db.Column(db.String(128))
    google_id = db.Column(db.String(128), nullable=True)

    def __init__(self, username, auth_type, google_id="false", email="false"):
        self.username = username
        self.auth_type = auth_type
        self.google_id = google_id
        self.email = email

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)