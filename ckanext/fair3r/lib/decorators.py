# encoding: utf-8
"""
Decorators for CKAN routes.

This module provides decorators for common route requirements
(e.g. authentication checks).
"""

from functools import wraps
import ckan.plugins.toolkit as toolkit


def login_required(redirect_to="user.login"):
    """
    Decorator to require user authentication for a route.

    If the user is not logged in, redirects to the specified route.
    Default redirect is to the user login page.

    Args:
        redirect_to (str): Route name to redirect to if user is not authenticated
    Returns:
        function: Decorated function that checks authentication before execution
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not toolkit.c.user:
                return toolkit.redirect_to(redirect_to)
            return func(*args, **kwargs)

        return wrapper

    return decorator
