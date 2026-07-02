"""Admin route tests for /admin/reset_credits.

Access requires BOTH an admin user AND the ADMIN_PASSWORD env secret matching
the submitted password. Anything else is a 403.
"""

from config import FREE_CREDITS_DEFAULT


def test_reset_credits_non_admin_correct_password_forbidden(client, make_user, login, monkeypatch):
    monkeypatch.setenv('ADMIN_PASSWORD', 'secret')
    make_user(username='regular', password='pw', is_admin=False)
    login('regular', 'pw')

    resp = client.post('/admin/reset_credits', data={'password': 'secret'})
    assert resp.status_code == 403


def test_reset_credits_admin_wrong_password_forbidden(client, make_user, login, monkeypatch):
    monkeypatch.setenv('ADMIN_PASSWORD', 'secret')
    make_user(username='admin', password='pw', is_admin=True)
    login('admin', 'pw')

    resp = client.post('/admin/reset_credits', data={'password': 'WRONG'})
    assert resp.status_code == 403


def test_reset_credits_admin_correct_password_ok(client, make_user, login, monkeypatch, db):
    monkeypatch.setenv('ADMIN_PASSWORD', 'secret')
    admin = make_user(username='admin', password='pw', is_admin=True, plan='free', free_credits=5)
    # a second user whose credits should also be reset
    other = make_user(username='other', plan='free', free_credits=0)
    login('admin', 'pw')

    resp = client.post('/admin/reset_credits', data={'password': 'secret'})
    assert resp.status_code == 200

    assert admin.free_credits == FREE_CREDITS_DEFAULT
    assert other.free_credits == FREE_CREDITS_DEFAULT
