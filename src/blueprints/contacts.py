"""Contacts CRUD routes."""

import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from src.extensions import db
from src.models.users import Contacts
from src.services.contact_service import create_user_contact
from src.utils.forms import form_get

logger = logging.getLogger(__name__)

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('/user-settings/contacts', methods=['GET'])
@login_required
def user_contacts():
    return render_template('user-contacts.html', contacts=current_user.contacts)


@contacts_bp.route('/add-contact', methods=['POST'])
@login_required
def add_contacts():
    try:
        # extract form information
        name = request.form.get('name')
        email = request.form.get('email')
        relationship = request.form.get('relationship', None)
        phone = request.form.get('phone', None)
        notes = request.form.get('notes', None)

        # add user contacts
        new_contact = create_user_contact(current_user.id, name, email, relationship, phone, notes)
        current_user.add_contact(new_contact)

        logger.info(new_contact)

        # check status and return response
        if not new_contact:
            return jsonify({'success': False, 'error': 'Failed to add contact'}), 400

        return jsonify({'success': True, 'contact': new_contact.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': f'An unexpected error has occurred: {e}'}), 500


@contacts_bp.route('/edit-contact/<int:contact_id>', methods=['PUT'])
@login_required
def edit_contact(contact_id):
    # retrieve contacts if they belong to the user
    contact = Contacts.query.get_or_404(contact_id)
    if contact.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    # extract data from form and change the fields
    name = form_get('name')
    email = form_get('email')
    if not name or not email:
        return jsonify({'success': False, 'error': 'Name and email are required'}), 400
    contact.name = name
    contact.email = email
    contact.relationship = form_get('relationship')
    contact.phone = form_get('phone')
    contact.notes = form_get('notes')

    db.session.commit()

    return jsonify({'success': True, 'contact': contact.to_dict()})


@contacts_bp.route('/delete-contact/<int:contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    # delete the contact only if it belongs to the user
    contact = Contacts.query.get_or_404(contact_id)
    if contact.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    db.session.delete(contact)
    db.session.commit()

    return jsonify({'success': True})
