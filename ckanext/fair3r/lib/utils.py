"""
Utility functions for the Fair3R extension.

This module contains common utility functions used across the extension.
"""

import os


def asbool(value):
    """
    Convert common string representations of truthy / falsy values to bools.

    This function handles various input types and string representations
    commonly used in configuration files (INI files, environment variables, etc.).

    Args:
        value: The value to convert to boolean. Can be:
            - bool: Returns as-is
            - None: Returns False
            - str: Checks if lowercase stripped value is in ('true', '1', 'yes', 'on')
            - other: Uses bool() conversion

    Returns:
        bool: The boolean representation of the value.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def resolve_schema_dir():
    """
    Directory that contains ``fdf_schema.json`` and ``i18n/``.

    In DEV Docker this is the mounted local clone of fair3r-fdf-schema when
    ``ckanext.fair3r.fdf_schema_dir`` (or ``CKANEXT_FAIR3R_FDF_SCHEMA_DIR``)
    points at a directory that actually contains the schema file. Otherwise
    the extension's bundled ``schema/`` directory is used.
    """
    plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bundled = os.path.join(plugin_dir, "schema")

    configured = ""
    try:
        from ckan.plugins import toolkit

        config = getattr(toolkit, "config", None) or {}
        try:
            value = config.get("ckanext.fair3r.fdf_schema_dir")
        except (AttributeError, TypeError, RuntimeError):
            value = None
        if value:
            configured = str(value).strip()
    except ImportError:
        pass

    if not configured:
        configured = os.environ.get("CKANEXT_FAIR3R_FDF_SCHEMA_DIR", "").strip()

    if configured and os.path.isfile(os.path.join(configured, "fdf_schema.json")):
        return configured
    return bundled


def get_schema_json_path():
    """
    Return the absolute path to the FDF schema JSON file.
    """
    return os.path.join(resolve_schema_dir(), "fdf_schema.json")
