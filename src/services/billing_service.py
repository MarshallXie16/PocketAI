"""Stripe fulfillment.

``handle_checkout_session`` runs from the webhook — there is no logged-in
session, so the user always comes from ``client_reference_id``, never
``current_user``. Idempotency (never double-granting on Stripe's retries) is
enforced by the caller via the StripeEvent table.
"""

import logging

import stripe

from config import PREMIUM_CREDITS_GRANT
from src.extensions import db
from src.models.users import User

logger = logging.getLogger(__name__)


def handle_checkout_session(checkout_session):
    """Fulfill a completed Stripe checkout session.

    NOTE: called from the webhook — the user always comes from
    client_reference_id, never current_user.
    """
    user_id = checkout_session['client_reference_id']
    user = User.query.get(user_id)
    if not user:
        logger.error('Stripe checkout for unknown user id %s', user_id)
        return

    user.stripe_customer_id = checkout_session['customer']

    # resolve the purchased price's lookup key
    session_with_line_item = stripe.checkout.Session.retrieve(
        checkout_session['id'],
        expand=['line_items'],
    )
    line_item = session_with_line_item['line_items']['data'][0]
    price = stripe.Price.retrieve(line_item['price']['id'])
    lookup_key = price['lookup_key']

    update_user_subscription(user, lookup_key)
    logger.info('Fulfilled checkout for user %s (plan: %s)', user_id, lookup_key)


def update_user_subscription(user, subscription_plan):
    """Apply a subscription plan to a user (grants paid credits for premium)."""
    if subscription_plan == 'premium':
        user.plan = 'premium'
        user.add_paid_credits(PREMIUM_CREDITS_GRANT)
    else:
        logger.error('Unknown subscription plan in Stripe fulfillment: %s', subscription_plan)
    db.session.commit()
