from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask import Flask

db = SQLAlchemy()
migrate = Migrate()
app = Flask(__name__,
            template_folder='src/templates',
            static_folder='src/static')

