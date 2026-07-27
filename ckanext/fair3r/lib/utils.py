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


def get_schema_json_path():
    """
    Return the absolute path to the FDF schema JSON file.
    """
    plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(plugin_dir, "schema", "fdf_schema.json")
