from flask_login import UserMixin
from src.utils.extensions import db, migrate
from werkzeug.security import generate_password_hash, check_password_hash

# many-to-many relationship between users and ai_models
user_ai = db.Table('user_ai',
                   db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
                   db.Column('ai_model_id', db.Integer, db.ForeignKey('ai_model.id'))
                   )

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(128), nullable=True)
    password_hash = db.Column(db.String(128), nullable=True)
    active = db.Column(db.Boolean, default=True)
    plan = db.Column(db.String(64), default='free')
    free_credits = db.Column(db.Integer, default=1500)
    paid_credits = db.Column(db.Integer, default=0)
    auth_type = db.Column(db.String(128))
    google_id = db.Column(db.String(128), nullable=True, unique=True)
    settings = db.relationship('UserSettings', backref='user', uselist=False, cascade='all, delete-orphan')
    ai_models = db.relationship('AIModel', secondary=user_ai, back_populates='users')
    messages = db.relationship('Message', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')

    def __init__(self, username, auth_type, email=None, google_id=None):
        self.username = username
        self.auth_type = auth_type
        self.email = email
        self.google_id = google_id

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def assign_ai_model(self, ai_model):
        if ai_model not in self.ai_models:
            self.ai_models.append(ai_model)

    def remove_ai_model(self, ai_model):
        if ai_model in self.ai_models:
            self.ai_models.remove(ai_model)

    # reset free credits to 1500 for free users (premium users don't have free credits)
    def reset_free_credits(self):
        self.free_credits = 100 if self.plan == 'free' else 0

    # add paid credits to a user's account
    def add_paid_credits(self, amount):
        """Add paid credits to the user's account."""
        self.paid_credits += amount

    # use credits; use free credits first, then paid credits
    def use_credits(self, amount):
        if self.free_credits >= amount:
            self.free_credits -= amount
        else:
            amount -= self.free_credits
            self.free_credits = 0
            self.paid_credits -= amount

# AI Model
class AIModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    model_name = db.Column(db.String(128), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    users = db.relationship('User', secondary=user_ai, back_populates='ai_models')
    settings = db.relationship('AISettings', backref='ai_model', uselist=False, cascade='all, delete-orphan')
    messages = db.relationship('Message', back_populates='ai_model', cascade='all, delete-orphan')
    
    def __init__(self, name, model_name, prompt, description=""):
        self.name = name
        self.model_name = model_name
        self.prompt = prompt
        self.description = description

    # assign user to model and vice versa
    def assign_user(self, user):
        if user not in self.users:
            self.users.append(user)



# User Settings model
class UserSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timezone = db.Column(db.String(64), nullable=True)
    messages_per_page = db.Column(db.Integer, default=20)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __init__(self, user_id, timezone="UTC", messages_per_page=10):
        self.user_id = user_id
        self.timezone = timezone
        self.messages_per_page = messages_per_page


# AI Settings model
class AISettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    memory_chunk_size = db.Column(db.Integer, default=256)
    ai_model_id = db.Column('ai_model_id', db.Integer, db.ForeignKey('ai_model.id'))

    def __init__(self, ai_model_id, memory_chunk_size=6):
        self.ai_model_id = ai_model_id
        self.memory_chunk_size = memory_chunk_size
