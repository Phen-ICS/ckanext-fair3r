# encoding: utf-8
"""
Fair3R extension library module.

This module contains utility functions and decorators for the Fair3R extension.
"""

from ckanext.fair3r.lib.decorators import login_required
from ckanext.fair3r.lib.utils import asbool

__all__ = ["login_required", "asbool"]
