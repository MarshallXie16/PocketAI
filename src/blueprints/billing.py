"""Billing routes: Stripe checkout, webhook fulfillment, cancellation, and the
payment result pages.

The webhook is the security-sensitive one: it verifies Stripe's signature and
is idempotent via the StripeEvent table (Stripe retries deliveries, so an
event is fulfilled at most once)."""

import logging
import os

import stripe
from flask import Blueprint, jsonify, redirect, render_template, request
from flask_login import current_user, login_required

from src.extensions import db
from src.models.billing import StripeEvent
from src.services.billing_service import handle_checkout_session

logger = logging.getLogger(__name__)

billing_bp = Blueprint('billing', __name__)


@billing_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    try:
        user_id = current_user.id
        your_domain = os.environ.get('YOUR_DOMAIN')
        # try to find price based on lookup key
        prices = stripe.Price.list(
            lookup_keys=[request.form['lookup_key']],
            expand=['data.product'],
        )

        # create checkout session
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': prices.data[0].id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            client_reference_id=user_id,
            success_url=your_domain + '/payment-success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=your_domain + '/payment-canceled',
        )
        # redirect to stripe hosted checkout page
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        logger.error(f'Subscription Purchase Error: {e}')
        return redirect('/error?message=Error creating subscription session.')


@billing_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    # raw data from stripe servers + signature proving it came from stripe
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        logger.warning('Rejected Stripe webhook with invalid payload/signature')
        return jsonify({'error': 'invalid signature'}), 400

    # idempotency: Stripe retries webhooks; never grant twice for one event
    if StripeEvent.query.filter_by(event_id=event['id']).first():
        return jsonify({'status': 'already processed'}), 200

    event_type = event['type']
    if event_type == 'checkout.session.completed':
        handle_checkout_session(event['data']['object'])
    elif event_type == 'customer.subscription.deleted':
        logger.info('Subscription canceled: %s', event['id'])
    else:
        logger.info('Unhandled Stripe event type: %s', event_type)

    db.session.add(StripeEvent(event_id=event['id']))
    db.session.commit()
    return jsonify({'status': 'success'})


@billing_bp.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    try:
        # Get the customer's Stripe ID
        customer = stripe.Customer.retrieve(current_user.stripe_customer_id)

        # Get the customer's active subscriptions
        subscriptions = stripe.Subscription.list(customer=customer.id, status='active')

        if not subscriptions.data:
            return jsonify({'error': 'User does not have any active subscriptions'}), 404

        # Cancel the first active subscription
        subscription = subscriptions.data[0]
        canceled_subscription = stripe.Subscription.delete(subscription.id)

        return jsonify({
            'status': 'success',
            'message': 'Subscription canceled successfully!',
            'subscription_id': canceled_subscription.id,
        })

    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        return jsonify({'error': 'An unexpected error occurred'}), 500


@billing_bp.route('/payment-success')
def success():
    session_id = request.args.get('session_id')
    session = stripe.checkout.Session.retrieve(session_id)
    return render_template('payment-success.html', session=session)


@billing_bp.route('/payment-canceled')
def cancel():
    return render_template('payment-canceled.html')
