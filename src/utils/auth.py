from authlib.integrations.flask_client import OAuth
from flask import current_app

oauth = OAuth()
google = None

def init_oauth(app):
    oauth.init_app(app)

    global google
    google = oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
        client_kwargs={
            'scope': 'openid email profile https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/calendar'
        }
    )
