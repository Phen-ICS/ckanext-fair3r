"""
Fair3R Custom Overlay Integration Blueprint

This blueprint handles the integration between CKAN and the Fair3R Custom Overlay (FCO)
application for dataset creation. It intercepts dataset creation requests and redirects
users to FCO with secure authentication tokens.
"""

import base64
import hashlib
import json
import logging
import time
import traceback
from urllib.parse import urlencode

from cryptography.fernet import Fernet

from flask import Blueprint, redirect, request, session, jsonify
import ckan.plugins.toolkit as toolkit
from ckan.lib import helpers as h
from ckan.model import User
from ckan.views.dataset import CreateView
from ckanext.fair3r.lib.decorators import login_required
from ckanext.fair3r.lib.utils import asbool

log = logging.getLogger(__name__)

fco_integration = Blueprint("fco_integration", __name__)


def _generate_secure_token(user_data, shared_secret):
    """
    Generate a secure token for transmitting user data to FCO.

    Uses symmetric encryption (AES) to encrypt the JSON data with the shared secret,
    ensuring that even if intercepted, the data cannot be read without the secret.

    Args:
        user_data (dict): User data to be transmitted
        shared_secret (str): Shared secret key between CKAN and FCO

    Returns:
        str: Base64 encoded secure token containing encrypted data and HMAC signature
    """
    # Add timestamp to prevent replay attacks
    user_data["timestamp"] = int(time.time())
    user_data["expires"] = int(time.time()) + 300  # 5 minutes expiration

    # Convert to JSON
    data_json = json.dumps(user_data, sort_keys=True)

    # Derive a 32-byte key from the shared secret using SHA256
    # Fernet requires a URL-safe base64-encoded 32-byte key
    key_material = hashlib.sha256(shared_secret.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_material)

    # Create Fernet cipher with the derived key
    fernet = Fernet(fernet_key)

    # Encrypt the JSON data (Fernet returns URL-safe base64-encoded bytes)
    encrypted_data_bytes = fernet.encrypt(data_json.encode("utf-8"))

    return base64.urlsafe_b64encode(encrypted_data_bytes).decode("utf-8")


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
            "ignore_auth": True  # Required for system operations
        }

        # Check if user already has the FCO Integration token specifically
        try:
            api_tokens = toolkit.get_action("api_token_list")(
                context, {"user_id": user.id}
            )

            # Look for existing FCO Integration token and revoke it
            fco_token = None
            for token in api_tokens:
                if (
                    isinstance(token, dict)
                    and token.get("name") == "FCO Integration Token"
                ):
                    fco_token = token
                    break

            if fco_token and "id" in fco_token:
                log.debug(
                    f"Found existing FCO Integration token for user {user.name}, revoking it"
                )
                # Revoke the existing token
                try:
                    toolkit.get_action("api_token_revoke")(
                        context, {"jti": fco_token["id"]}
                    )
                    log.debug(
                        f"Successfully revoked existing FCO Integration token for user {user.name}"
                    )
                except Exception as e:
                    log.warning(f"Could not revoke existing token: {e}")

        except Exception as e:
            log.debug(
                f"Could not list existing tokens (will create new FCO token): {e}"
            )

        # Create a new FCO Integration token
        log.debug(f"Creating new FCO Integration token for user {user.name}")
        token_data = {
            "user": user.name,  # Use username, not user_id
            "name": "FCO Integration Token",
        }
        api_token_response = toolkit.get_action("api_token_create")(context, token_data)
        log.debug(f"FCO Integration token creation response: {api_token_response}")

        # The response should be a dict with 'token' key
        if isinstance(api_token_response, dict) and "token" in api_token_response:
            return api_token_response["token"]
        else:
            log.error(f"Unexpected API token response format: {api_token_response}")
            return None

    except Exception as e:
        log.error(
            f"Error getting FCO Integration token for user {user.name} ({user.id}): {e}"
        )
        log.error(f"Traceback: {traceback.format_exc()}")
        return None


@fco_integration.route("/dataset/new/fco")
@login_required(redirect_to="user.login")
def fco_dataset_creation():
    """
    Redirect to FCO for dataset creation.

    This route redirects authenticated users to the Fair3R Custom Overlay
    application for enhanced dataset creation functionality.
    """

    enable_fco = asbool(
        toolkit.config.get("ckanext.fair3r.enable_fco_integration", False)
    )
    if not enable_fco:
        return CreateView().get(package_type="dataset")

    user = User.get(toolkit.c.user)
    log.info(f"User {user.name} attempt to access FCO")

    try:
        # Get FCO configuration
        fco_url = toolkit.config.get("ckanext.fair3r.fco_url")
        shared_secret = toolkit.config.get("ckanext.fair3r.shared_secret")

        if not fco_url or not shared_secret:
            log.error("FCO integration not properly configured")
            raise RuntimeError("FCO integration not properly configured")

        # Get or create API token
        api_token = _get_user_api_token(user)
        if not api_token:
            log.error(f"Could not get API token for user {user.name} ({user.id})")
            raise RuntimeError(
                f"Could not get API token for user {user.name} ({user.id})"
            )

        # Prepare user data for transmission
        user_data = {
            "user_id": user.id,
            "username": user.name,
            "email": user.email,
            "fullname": user.fullname,
            "api_token": api_token,
        }

        # Generate secure token
        secure_token = _generate_secure_token(user_data, shared_secret)

        # Build redirect URL
        # Include current CKAN language so FCO can match the UI language
        current_lang = h.lang() or ""
        redirect_params = {
            "token": secure_token,
            "source": "ckan",
            "action": "create_dataset",
        }
        if current_lang:
            redirect_params["lang"] = current_lang

        fco_redirect_url = f"{fco_url}/ckan/integration?{urlencode(redirect_params)}"

        log.info(f"Redirecting user {user.name} to FCO for dataset creation")
        return redirect(fco_redirect_url)

    except Exception as e:
        log.error(f"Error in FCO integration redirect: {e}")
        raise


@fco_integration.route("/dataset/new/ckan", methods=["GET", "POST"])
def ckan_dataset_creation():
    """
    Direct access to CKAN dataset creation (bypassing FCO).

    This route allows users to access the standard CKAN dataset creation
    interface even when FCO integration is enabled.
    """
    if request.method == "POST":
        return CreateView().post(package_type="dataset")
    return CreateView().get(package_type="dataset")


@fco_integration.route("/dataset/new/standard", methods=["GET", "POST"])
def standard_dataset_creation():
    """
    Direct access to standard CKAN dataset creation.

    This route provides direct access to the standard CKAN dataset creation
    interface, bypassing the choice page.
    """
    if request.method == "POST":
        return CreateView().post(package_type="dataset")
    return CreateView().get(package_type="dataset")


@fco_integration.route("/fco/status")
def fco_status():
    """
    Health check endpoint for FCO integration.

    Returns basic information about the FCO integration status.
    """
    try:
        status = {
            "enabled": toolkit.config.get(
                "ckanext.fair3r.enable_fco_integration", False
            ),
            "fco_url": toolkit.config.get("ckanext.fair3r.fco_url"),
            "context": toolkit.config.get("ckanext.fair3r.context"),
            "ckan_site_url": toolkit.config.get("ckan.site_url"),
            "user_authenticated": bool(toolkit.c.user),
        }

        return jsonify(status)

    except Exception as e:
        log.error(f"Error in FCO status check: {e}")
        return jsonify({"error": str(e)}), 500


@fco_integration.route("/user/logout")
def logout():
    """
    Handle logout from CKAN and also logout from FCO.

    This route intercepts CKAN logout and ensures the user is also logged out
    from FCO. It prevents infinite loops by checking the 'from' query parameter.
    """

    # If no user is authenticated, redirect to login
    if not toolkit.c.user:
        return redirect(toolkit.url_for("user.login"))

    # If logout is coming from FCO, just perform CKAN logout and redirect to home
    log.info("Logout from FCO - performing CKAN logout only")
    # Clear CKAN session
    session.clear()

    enable_fco = asbool(
        toolkit.config.get("ckanext.fair3r.enable_fco_integration", False)
    )
    fco_url = toolkit.config.get("ckanext.fair3r.fco_url")

    # If FCO integration is enabled, redirect to FCO logout
    if enable_fco:
        log.info("Redirecting to FCO logout")
        # Redirect to FCO logout with 'from=ckan' parameter to prevent loop
        fco_logout_url = f"{fco_url}/logout"
        return redirect(fco_logout_url)

    # If FCO is not enabled, just redirect to CKAN home
    return redirect(toolkit.url_for("home.index"))
