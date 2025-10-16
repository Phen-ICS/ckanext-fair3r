"""
Fair3R Custom Overlay Integration Blueprint

This blueprint handles the integration between CKAN and the Fair3R Custom Overlay (FCO)
application for dataset creation. It intercepts dataset creation requests and redirects
users to FCO with secure authentication tokens.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import urlencode

from flask import Blueprint, current_app, redirect, request, session, url_for, jsonify
import ckan.plugins.toolkit as toolkit
from ckan.lib import helpers as h
from ckan.model import User
import ckan.lib.mailer as ckan_mailer

log = logging.getLogger(__name__)

fco_integration = Blueprint('fco_integration', __name__)


def _asbool(value):
    """Convert common string representations of truthy / falsy values to bools."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes', 'on')
    return bool(value)


def _generate_secure_token(user_data, shared_secret):
    """
    Generate a secure token for transmitting user data to FCO.
    
    Args:
        user_data (dict): User data to be transmitted
        shared_secret (str): Shared secret key between CKAN and FCO
    
    Returns:
        str: Base64 encoded secure token
    """
    # Add timestamp to prevent replay attacks
    user_data['timestamp'] = int(time.time())
    user_data['expires'] = int(time.time()) + 300  # 5 minutes expiration
    
    # Convert to JSON and encode
    data_json = json.dumps(user_data, sort_keys=True)
    data_encoded = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
    
    # Create HMAC signature
    signature = hmac.new(
        shared_secret.encode('utf-8'),
        data_encoded.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Combine data and signature
    token = f"{data_encoded}.{signature}"
    return base64.b64encode(token.encode('utf-8')).decode('utf-8')


def _get_user_api_token(user):
    """
    Get or create an API token for the user.
    
    Args:
        user: User object
    
    Returns:
        str: API token
    """
    try:
        # Create context for API actions - need to use ignore_auth for system operations
        context = {
            'ignore_auth': True  # Required for system operations
        }
        
        # Check if user already has the FCO Integration token specifically
        try:
            api_tokens = toolkit.get_action('api_token_list')(context, {'user_id': user.id})
            
            # Look for existing FCO Integration token and revoke it
            fco_token = None
            for token in api_tokens:
                if isinstance(token, dict) and token.get('name') == 'FCO Integration Token':
                    fco_token = token
                    break
            
            if fco_token and 'id' in fco_token:
                log.debug(f"Found existing FCO Integration token for user {user.name}, revoking it")
                # Revoke the existing token
                try:
                    toolkit.get_action('api_token_revoke')(context, {'jti': fco_token['id']})
                    log.debug(f"Successfully revoked existing FCO Integration token for user {user.name}")
                except Exception as e:
                    log.warning(f"Could not revoke existing token: {e}")
                
        except Exception as e:
            log.debug(f"Could not list existing tokens (will create new FCO token): {e}")
        
        # Create a new FCO Integration token
        log.debug(f"Creating new FCO Integration token for user {user.name}")
        token_data = {
            'user': user.name,  # Use username, not user_id
            'name': 'FCO Integration Token'
        }
        api_token_response = toolkit.get_action('api_token_create')(context, token_data)
        log.debug(f"FCO Integration token creation response: {api_token_response}")
        
        # The response should be a dict with 'token' key
        if isinstance(api_token_response, dict) and 'token' in api_token_response:
            return api_token_response['token']
        else:
            log.error(f"Unexpected API token response format: {api_token_response}")
            return None
            
    except Exception as e:
        import traceback
        log.error(f"Error getting FCO Integration token for user {user.name} ({user.id}): {e}")
        log.error(f"Traceback: {traceback.format_exc()}")
        return None


@fco_integration.route('/dataset/new')
def dataset_creation_choice():
    """
    Show dataset creation choice page.
    
    This route shows a choice between standard CKAN form and FCO interface.
    Only superadmins can see the FCO option.
    """
    # Evaluate configuration flags
    enable_fco = _asbool(toolkit.config.get('ckanext.fair3r.enable_fco_integration', False))
    context_env = (toolkit.config.get('ckanext.fair3r.context', '') or '').lower()

    # If the integration is disabled just fall back to the normal CKAN flow
    if not enable_fco:
        from ckan.views.dataset import CreateView
        return CreateView().get(package_type='dataset')

    # In production we temporarily redirect to the custom CKAN form and skip the choice page
    # (FCO interface not yet finished)
    if context_env in ('PROD','prod', 'production'):
        return toolkit.redirect_to('fco_integration.ckan_dataset_creation')
        #return toolkit.redirect_to('fco_integration.redirect_to_fco_dataset_creation')

    # For visitors (not logged in), redirect to account request page instead of login
    if not toolkit.c.user:
        return toolkit.redirect_to('account_request.request_account')

    # Render the choice template with necessary context
    return toolkit.render('package/creation_choice.html', {
        'pkg_dict': None,
        'dataset_type': 'dataset'
    })


@fco_integration.route('/dataset/new/fco')
def redirect_to_fco_dataset_creation():
    """
    Redirect to FCO for dataset creation.
    
    This route redirects authenticated users to the Fair3R Custom Overlay 
    application for enhanced dataset creation functionality.
    """
    # Check if FCO integration is enabled
    if not toolkit.config.get('ckanext.fair3r.enable_fco_integration', False):
        # If disabled, proceed with normal CKAN dataset creation
        from ckan.views.dataset import CreateView
        return CreateView().get(package_type='dataset')
    
    # Check if user is authenticated
    if not toolkit.c.user:
        # Redirect to login if not authenticated
        return toolkit.redirect_to('user.login')
    
    # Allow everyone in production, otherwise restrict to superadmins
    context_env = (toolkit.config.get('ckanext.fair3r.context', '') or '').lower()
    from ckan.model import User
    user = User.get(toolkit.c.user)
    if context_env not in ('prod', 'production') and (not user or not user.sysadmin):
        log.warning(f"Non-superadmin user {toolkit.c.user} attempted to access FCO")
        return toolkit.redirect_to('fco_integration.dataset_creation_choice')
    
    try:
        # Get FCO configuration
        fco_url = toolkit.config.get('ckanext.fair3r.fco_url')
        shared_secret = toolkit.config.get('ckanext.fair3r.shared_secret')
        
        if not fco_url or not shared_secret:
            log.error("FCO integration not properly configured")
            raise RuntimeError("FCO integration not properly configured")
        
        # Get or create API token
        api_token = _get_user_api_token(user)
        if not api_token:
            log.error(f"Could not get API token for user {user.name} ({user.id})")
            raise RuntimeError(f"Could not get API token for user {user.name} ({user.id})")
        
        # Prepare user data for transmission
        user_data = {
            'user_id': user.id,
            'username': user.name,
            'email': user.email,
            'fullname': user.fullname,
            'api_token': api_token,
            'ckan_site_url': toolkit.config.get('ckan.site_url'),
            'return_url': request.args.get('return_url', '')
        }
        
        # Generate secure token
        secure_token = _generate_secure_token(user_data, shared_secret)
        
        # Build redirect URL
        # Include current CKAN language so FCO can match the UI language
        current_lang = h.lang() or ''
        redirect_params = {
            'token': secure_token,
            'source': 'ckan',
            'action': 'create_dataset'
        }
        if current_lang:
            redirect_params['lang'] = current_lang
        
        fco_redirect_url = f"{fco_url}/ckan/integration?{urlencode(redirect_params)}"
        
        log.info(f"Redirecting superadmin user {user.name} to FCO for dataset creation")
        return redirect(fco_redirect_url)
        
    except Exception as e:
        log.error(f"Error in FCO integration redirect: {e}")
        raise


@fco_integration.route('/dataset/new/ckan', methods=['GET', 'POST'])
def ckan_dataset_creation():
    """
    Direct access to CKAN dataset creation (bypassing FCO).
    
    This route allows users to access the standard CKAN dataset creation
    interface even when FCO integration is enabled.
    """
    from ckan.views.dataset import CreateView
    if request.method == 'POST':
        return CreateView().post(package_type='dataset')
    return CreateView().get(package_type='dataset')


@fco_integration.route('/dataset/new/standard', methods=['GET', 'POST'])
def standard_dataset_creation():
    """
    Direct access to standard CKAN dataset creation.
    
    This route provides direct access to the standard CKAN dataset creation
    interface, bypassing the choice page.
    """
    from ckan.views.dataset import CreateView
    if request.method == 'POST':
        return CreateView().post(package_type='dataset')
    return CreateView().get(package_type='dataset')


@fco_integration.route('/fco/status')
def fco_status():
    """
    Health check endpoint for FCO integration.
    
    Returns basic information about the FCO integration status.
    """
    try:
        status = {
            'enabled': toolkit.config.get('ckanext.fair3r.enable_fco_integration', False),
            'fco_url': toolkit.config.get('ckanext.fair3r.fco_url'),
            'context': toolkit.config.get('ckanext.fair3r.context'),
            'ckan_site_url': toolkit.config.get('ckan.site_url'),
            'user_authenticated': bool(toolkit.c.user)
        }
        
        return jsonify(status)
        
    except Exception as e:
        log.error(f"Error in FCO status check: {e}")
        return jsonify({'error': str(e)}), 500 


# Account request route moved to its own blueprint (account_request)