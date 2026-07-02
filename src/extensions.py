"""Shared Flask extension singletons.

These are instantiated here (unbound) and wired to the app inside
``create_app`` (``src/app_factory.py``). Importing this module never touches
the app, which keeps model/service imports free of circular dependencies.
"""

from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
oauth = OAuth()
