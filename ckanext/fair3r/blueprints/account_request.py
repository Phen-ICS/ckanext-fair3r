# encoding: utf-8
from __future__ import annotations

import logging

from flask import Blueprint, request

import ckan.plugins.toolkit as toolkit
from ckan.common import _
import ckan.lib.mailer as mailer


log = logging.getLogger(__name__)


account_request_bp = Blueprint('fair3r_account_request', __name__)


@account_request_bp.route('/fair3r/account-request/submit', methods=['POST'])
def submit() -> str:
    toolkit.check_access('site_read', {})

    email = request.form.get('email', '').strip()
    name = request.form.get('name', '').strip()
    message = request.form.get('message', '').strip()
    source_path = request.form.get('source_path', '/')

    if not email or not name or not message:
        toolkit.h.flash_error(_('Please fill in all required fields.'))
        return toolkit.h.redirect_to(source_path or '/')

    # Determine destination email from config. Prefer CKAN core email_to when set.
    config = toolkit.config
    recipient_email = (
        config.get('email_to')
        or config.get('ckanext.fair3r.contact_email')
        or config.get('smtp.mail_from')
    )

    if not recipient_email:
        log.error('No recipient email configured for account requests')
        toolkit.h.flash_error(_('No recipient email configured.'))
        return toolkit.h.redirect_to(source_path or '/')

    subject = _('New account request from {name}').format(name=name)
    body = (
        f"Account request submitted from CKAN site.\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"From path: {source_path}\n\n"
        f"Message:\n{message}\n"
    )

    try:
        mailer.mail_recipient(name, recipient_email, subject, body, body_html=None)
        toolkit.h.flash_success(_('Your request has been sent. We will contact you shortly.'))
    except Exception:
        log.exception('Failed to send account request email')
        toolkit.h.flash_error(_('Failed to send your request. Please try again later.'))

    return toolkit.h.redirect_to(source_path or '/')


