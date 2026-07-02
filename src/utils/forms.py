"""Form-parsing helpers."""

from flask import request


def form_get(field, default=''):
    """Read a form field as a stripped string, tolerating missing fields.

    The old pattern of calling ``.strip()`` directly on ``request.form.get()``
    raised AttributeError (a 500) whenever a field was absent from the POST
    body (BUG-10).
    """
    value = request.form.get(field)
    return value.strip() if isinstance(value, str) else default
