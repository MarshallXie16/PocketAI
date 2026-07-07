"""Billing models.

Defines StripeEvent, a record of processed Stripe webhook event ids used to make
credit fulfillment idempotent across Stripe's delivery retries.
"""

import datetime

from src.extensions import db


class StripeEvent(db.Model):
    """Processed Stripe webhook event ids.

    Stripe retries webhook delivery; recording processed event ids makes
    fulfillment idempotent so a retry never double-grants credits.
    """

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(256), unique=True, nullable=False, index=True)
    processed_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    def __init__(self, event_id):
        self.event_id = event_id
