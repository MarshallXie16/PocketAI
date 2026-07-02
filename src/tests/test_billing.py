"""Billing / Stripe webhook tests.

Everything Stripe is mocked at the boundary (stripe.Webhook.construct_event,
stripe.checkout.Session.retrieve, stripe.Price.retrieve) so no network / keys
are needed. The webhook's security properties under test: reject bad
signatures, fulfill legitimate events, and stay idempotent on Stripe retries.
"""

from unittest.mock import patch

import stripe

from config import PREMIUM_CREDITS_GRANT
from src.models.billing import StripeEvent
from src.models.users import User


def test_webhook_invalid_signature_returns_400(client):
    with patch('stripe.Webhook.construct_event',
               side_effect=stripe.error.SignatureVerificationError('bad sig', 'sig-header')):
        resp = client.post('/webhook', data=b'{}', headers={'Stripe-Signature': 'nope'})
    assert resp.status_code == 400


def _premium_event(user_id, event_id='evt_1'):
    return {
        'id': event_id,
        'type': 'checkout.session.completed',
        'data': {'object': {
            'id': 'cs_test_1',
            'client_reference_id': user_id,
            'customer': 'cus_123',
        }},
    }


def _retrieve_with_line_items(*args, **kwargs):
    return {'line_items': {'data': [{'price': {'id': 'price_123'}}]}}


def _price_retrieve(*args, **kwargs):
    return {'lookup_key': 'premium'}


def test_webhook_fulfillment_grants_premium(client, make_user):
    user = make_user(username='payer', paid_credits=0, plan='free')
    uid = user.id

    with patch('stripe.Webhook.construct_event', return_value=_premium_event(uid)), \
         patch('stripe.checkout.Session.retrieve', side_effect=_retrieve_with_line_items), \
         patch('stripe.Price.retrieve', side_effect=_price_retrieve):
        resp = client.post('/webhook', data=b'{}', headers={'Stripe-Signature': 'ok'})

    assert resp.status_code == 200
    refreshed = User.query.get(uid)
    assert refreshed.plan == 'premium'
    assert refreshed.paid_credits == PREMIUM_CREDITS_GRANT
    assert refreshed.stripe_customer_id == 'cus_123'
    assert StripeEvent.query.filter_by(event_id='evt_1').count() == 1


def test_webhook_replay_is_noop(client, make_user):
    user = make_user(username='payer', paid_credits=0, plan='free')
    uid = user.id

    def _fire():
        with patch('stripe.Webhook.construct_event', return_value=_premium_event(uid)), \
             patch('stripe.checkout.Session.retrieve', side_effect=_retrieve_with_line_items), \
             patch('stripe.Price.retrieve', side_effect=_price_retrieve):
            return client.post('/webhook', data=b'{}', headers={'Stripe-Signature': 'ok'})

    first = _fire()
    assert first.status_code == 200
    assert User.query.get(uid).paid_credits == PREMIUM_CREDITS_GRANT

    # Replaying the same event id must not double-grant (StripeEvent idempotency)
    second = _fire()
    assert second.status_code == 200
    assert second.get_json()['status'] == 'already processed'
    assert User.query.get(uid).paid_credits == PREMIUM_CREDITS_GRANT
    assert StripeEvent.query.filter_by(event_id='evt_1').count() == 1


def test_add_credits_route_removed_returns_404(client, make_user, login):
    # the self-serve /add-credits/<amount> route was deliberately removed
    make_user(username='u', password='pw')
    login('u', 'pw')
    resp = client.get('/add-credits/999')
    assert resp.status_code == 404
