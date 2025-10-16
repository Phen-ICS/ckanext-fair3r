import logging

from flask import Blueprint, request
import ckan.plugins.toolkit as toolkit
from ckan.lib import helpers as h
import ckan.lib.mailer as ckan_mailer

log = logging.getLogger(__name__)

account_request_bp = Blueprint('account_request', __name__)


@account_request_bp.route('/account/request', methods=['GET', 'POST'])
def request_account():
    """
    Render a page inviting visitors to contact us to create a new account.

    Displays a form with email, name and message. On submit, sends an email
    to the configured contact address.
    """
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        name = (request.form.get('name') or '').strip()
        message = (request.form.get('message') or '').strip()

        errors = []
        if not email:
            errors.append('email')
        if not name:
            errors.append('name')
        if not message:
            errors.append('message')

        if errors:
            h.flash_error(toolkit._('Please fill in all required fields.'))
            return toolkit.render('account/request_account.html', {
                'email': email,
                'name': name,
                'text': message
            })

        recipient_email = toolkit.config.get('ckanext.contact.mail_to')
        if not recipient_email:
            recipient_email = toolkit.config.get('smtp.mail_from') or toolkit.config.get('email_to')

        try:
            subject = f"Account request from {name}"
            body = (
                f"A visitor requested an account on {toolkit.config.get('ckan.site_title')}\n\n"
                f"Name: {name}\n"
                f"Email: {email}\n\n"
                f"Message:\n{message}\n"
            )
            body_html = (
                f"<p>A visitor requested an account on <strong>{toolkit.config.get('ckan.site_title')}</strong>.</p>"
                f"<p><strong>Name:</strong> {h.escape(name)}<br>"
                f"<strong>Email:</strong> {h.escape(email)}</p>"
                f"<p><strong>Message:</strong><br>{h.render_markdown(message)}</p>"
            )

            ckan_mailer.mail_recipient(
                recipient_name='FAIR3R Contact',
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                body_html=body_html
            )

            h.flash_success(toolkit._('Your request has been sent. We will contact you soon.'))
            return toolkit.redirect_to('home.index')
        except Exception as e:
            log.error(f"Error sending account request email: {e}")
            h.flash_error(toolkit._('There was a problem sending your request. Please try again later.'))

    return toolkit.render('account/request_account.html')


@account_request_bp.app_errorhandler(403)
def handle_forbidden(error):
    """
    Redirect to the account request page when users are forbidden to create datasets.

    Triggers when the 403 error message includes "Unauthorized to create a package"
    or when the path is a known dataset creation path. Prevents redirect loops.
    """
    try:
        # Avoid redirect loop if already on the account request page
        if request.endpoint == 'account_request.request_account' or request.path.startswith('/account/request'):
            return error

        description = getattr(error, 'description', '') or ''
        message = str(description or error or '')
        lower_msg = message.lower()

        is_dataset_new_path = request.path in (
            '/dataset/new',
            '/dataset/new/ckan',
            '/dataset/new/standard'
        )

        if is_dataset_new_path or 'unauthorized to create a package' in lower_msg:
            return toolkit.redirect_to('account_request.request_account')
    except Exception:
        # If anything goes wrong, fall back to default handling
        pass

    return error


