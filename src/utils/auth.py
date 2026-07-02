from authlib.integrations.flask_client import OAuth

oauth = OAuth()


def init_oauth(app):
    """Register the Google OAuth client on the shared OAuth extension.

    Use oauth.create_client('google') to get the client — the old module-level
    `google` global was permanently None for importers (BUG-11).
    """
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
        client_kwargs={
            'scope': 'openid email profile https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/calendar'
        }
    )
