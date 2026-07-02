"""Contacts CRUD + cross-user authorization tests."""

from src.models.users import Contacts


def _add_contact(client, name='Jane', email='jane@example.com', **extra):
    data = {'name': name, 'email': email}
    data.update(extra)
    return client.post('/add-contact', data=data)


def test_add_contact(client, make_user, login):
    make_user(username='u', password='pw')
    login('u', 'pw')

    resp = _add_contact(client, relationship='friend', phone='123', notes='n')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['contact']['name'] == 'Jane'
    assert Contacts.query.count() == 1


def test_edit_contact(client, make_user, login):
    make_user(username='u', password='pw')
    login('u', 'pw')
    cid = _add_contact(client).get_json()['contact']['id']

    resp = client.put(f'/edit-contact/{cid}', data={'name': 'Janet', 'email': 'janet@example.com'})
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True
    assert Contacts.query.get(cid).name == 'Janet'


def test_delete_contact(client, make_user, login):
    make_user(username='u', password='pw')
    login('u', 'pw')
    cid = _add_contact(client).get_json()['contact']['id']

    resp = client.delete(f'/delete-contact/{cid}')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True
    assert Contacts.query.get(cid) is None


def test_edit_missing_fields_returns_400(client, make_user, login):
    make_user(username='u', password='pw')
    login('u', 'pw')
    cid = _add_contact(client).get_json()['contact']['id']

    # missing email
    resp = client.put(f'/edit-contact/{cid}', data={'name': 'OnlyName'})
    assert resp.status_code == 400
    # missing name
    resp = client.put(f'/edit-contact/{cid}', data={'email': 'x@example.com'})
    assert resp.status_code == 400


def test_cross_user_edit_forbidden(client, make_user, login):
    owner = make_user(username='owner', password='pw')
    make_user(username='intruder', password='pw2')
    # create a contact owned by 'owner' directly
    contact = Contacts(name='Secret', email='secret@example.com', user_id=owner.id)
    from src.extensions import db
    db.session.add(contact)
    db.session.commit()
    cid = contact.id

    login('intruder', 'pw2')
    resp = client.put(f'/edit-contact/{cid}', data={'name': 'Hacked', 'email': 'h@example.com'})
    assert resp.status_code == 403
    assert Contacts.query.get(cid).name == 'Secret'


def test_cross_user_delete_forbidden(client, make_user, login):
    owner = make_user(username='owner', password='pw')
    make_user(username='intruder', password='pw2')
    from src.extensions import db
    contact = Contacts(name='Secret', email='secret@example.com', user_id=owner.id)
    db.session.add(contact)
    db.session.commit()
    cid = contact.id

    login('intruder', 'pw2')
    resp = client.delete(f'/delete-contact/{cid}')
    assert resp.status_code == 403
    assert Contacts.query.get(cid) is not None
