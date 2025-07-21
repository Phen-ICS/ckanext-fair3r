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

from flask import Blueprint, current_app, redirect, request, session, url_for
import ckan.plugins.toolkit as toolkit
from ckan.lib import helpers as h
from ckan.model import User

log = logging.getLogger(__name__)

fco_integration = Blueprint('fco_integration', __name__)


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
        # Create context for API actions - need to use ignore_auth for system actions
        context = {
            'ignore_auth': True  # Required for system operations
        }
        
        # Check if user already has the FCO Integration token specifically
        try:
            api_tokens = toolkit.get_action('api_token_list')(context, {'user_id': user.id})
            
            # Look for existing FCO Integration token
            fco_token = None
            for token in api_tokens:
                if isinstance(token, dict) and token.get('name') == 'FCO Integration Token':
                    fco_token = token
                    break
            
            if fco_token and 'id' in fco_token:
                log.debug(f"Found existing FCO Integration token for user {user.name}")
                return fco_token['id']
                
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
def redirect_to_fco_dataset_creation():
    """
    Intercept dataset creation requests and redirect to FCO.
    
    This route intercepts the standard CKAN dataset creation page and redirects
    authenticated users to the Fair3R Custom Overlay application for enhanced
    dataset creation functionality.
    """
    # Check if FCO integration is enabled
    if not toolkit.config.get('ckanext.fair3r.enable_fco_integration', False):
        # If disabled, proceed with normal CKAN dataset creation
        return toolkit.render('package/new.html')
    
    # Check if user is authenticated
    if not toolkit.c.user:
        # Redirect to login if not authenticated
        return toolkit.redirect_to('user.login')
    
    try:
        # Get FCO configuration
        fco_url = toolkit.config.get('ckanext.fair3r.fco_url')
        shared_secret = toolkit.config.get('ckanext.fair3r.shared_secret')
        
        if not fco_url or not shared_secret:
            log.error("FCO integration not properly configured")
            raise RuntimeError("FCO integration not properly configured")
        
        # Get current user information
        user = User.get(toolkit.c.user)
        if not user:
            log.error(f"User {toolkit.c.user} not found")
            raise LookupError(f"User {toolkit.c.user} not found")
        
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
        redirect_params = {
            'token': secure_token,
            'source': 'ckan',
            'action': 'create_dataset'
        }
        
        fco_redirect_url = f"{fco_url}/ckan/integration?{urlencode(redirect_params)}"
        
        log.info(f"Redirecting user {user.name} to FCO for dataset creation")
        return redirect(fco_redirect_url)
        
    except Exception as e:
        log.error(f"Error in FCO integration redirect: {e}")
        raise


@fco_integration.route('/dataset/new/ckan')
def ckan_dataset_creation():
    """
    Direct access to CKAN dataset creation (bypassing FCO).
    
    This route allows users to access the standard CKAN dataset creation
    interface even when FCO integration is enabled.
    """
    from ckan.views.dataset import CreateView
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
        
        return toolkit.jsonify(status)
        
    except Exception as e:
        log.error(f"Error in FCO status check: {e}")
        return toolkit.jsonify({'error': str(e)}), 500 