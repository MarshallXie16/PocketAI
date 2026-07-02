"""Auth route tests: signup, login validation, and anonymous access gating."""

from src.models.users import User


def test_signup_happy_path(client, db):
    resp = client.post('/signup', data={
        'username': 'alice',
        'email': 'alice@example.com',
        'password': 'secret123',
        'confirm-password': 'secret123',
    })
    # signup logs the user in and redirects into the onboarding flow
    assert resp.status_code == 302
    assert '/onboarding/user' in resp.headers['Location']

    user = User.query.filter_by(username='alice').first()
    assert user is not None
    assert user.email == 'alice@example.com'
    assert user.check_password('secret123')


def test_signup_duplicate_username_rejected(client, make_user):
    make_user(username='bob', email='bob@example.com')

    resp = client.post('/signup', data={
        'username': 'bob',
        'email': 'other@example.com',
        'password': 'secret123',
        'confirm-password': 'secret123',
    })
    # re-renders the signup page (200), does not redirect to onboarding
    assert resp.status_code == 200
    assert b'Username already exists.' in resp.data
    # still exactly one bob
    assert User.query.filter_by(username='bob').count() == 1


def test_login_wrong_password_rejected(client, make_user):
    make_user(username='carol', password='rightpass')

    resp = client.post('/login', data={'username': 'carol', 'password': 'wrongpass'})
    assert resp.status_code == 200
    assert b'Invalid username or password.' in resp.data


def test_chat_anonymous_redirects(client):
    resp = client.get('/chat')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_send_message_anonymous_redirects(client):
    resp = client.post('/send_message', json={'message': 'hi', 'modelId': 1})
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']
