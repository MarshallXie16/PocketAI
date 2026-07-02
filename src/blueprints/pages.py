"""Static content pages: homepage, pricing, legal, and the legacy error page."""

from flask import Blueprint, render_template, request

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def home():
    return render_template('index.html')


@pages_bp.route('/pricing')
def pricing():
    return render_template('pricing.html')


@pages_bp.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy-policy.html')


@pages_bp.route('/terms-of-service')
def terms_of_service():
    return render_template('terms-of-service.html')


# (DEPRECATED) displays error page with custom message
@pages_bp.route('/error', methods=['GET'])
def error():
    message = request.args.get('message', 'An error has occurred!')
    return render_template('error.html', message=message)
