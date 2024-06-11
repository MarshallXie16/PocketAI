# from flask import Flask
# from src.utils.extensions import db, migrate, oauth, login_manager
# from utils.config import Config

# def create_app():
#     app = Flask(__name__,
#                 template_folder='src/templates',
#                 static_folder='src/static')
#     app.config.from_object(Config)

#     db.init_app(app)
#     migrate.init_app(app, db)
#     oauth.init_app(app)
#     login_manager.init_app(app)

#     # Configure Google OAuth
#     oauth.register(
#         name='google',
#         client_id=app.config['GOOGLE_CLIENT_ID'],
#         client_secret=app.config['GOOGLE_CLIENT_SECRET'],
#         server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
#         client_kwargs={'scope': 'openid email profile https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/calendar'}
#     )

#     # Import and register Blueprints or other app components here
#     # from .routes import main_blueprint
#     # app.register_blueprint(main_blueprint)

#     return app
