"""
FDF schema loading utilities.
"""

import json
import logging

from flask import has_request_context, request
from ckan.lib import i18n


from ckanext.fair3r.lib.utils import get_schema_json_path
from ckanext.fair3r.lib.fdf.schema_i18n import (
    apply_schema_i18n,
    load_schema_i18n_catalog,
)

log = logging.getLogger(__name__)

__all__ = ["load_fdf_schema"]


def _load_raw_fdf_schema():
    try:
        with open(get_schema_json_path(), "r", encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
    except Exception as err:
        log.error("Failed to load FDF schema: %s", err, exc_info=True)
        return {"sections": [], "apis": {}, "vocabularies": {}}

    if not isinstance(schema, dict):
        log.error("Invalid FDF schema root type: %s", type(schema).__name__)
        return {"sections": [], "apis": {}, "vocabularies": {}}

    if not isinstance(schema.get("sections"), list):
        log.error("Invalid FDF schema: sections must be a list")
        schema["sections"] = []

    if not isinstance(schema.get("apis"), dict):
        schema["apis"] = {}

    if not isinstance(schema.get("vocabularies"), dict):
        schema["vocabularies"] = {}

    return schema


def _resolve_locale(locale=None):
    if locale:
        return str(locale).split("_")[0].lower()

    if has_request_context():
        lang = request.environ.get("CKAN_LANG")
        if lang:
            return str(lang).split("_")[0].lower()

    try:
        lang = i18n.get_lang()
        if lang:
            return str(lang).split("_")[0].lower()
    except RuntimeError:
        log.debug("No CKAN application context")

    return "en"


def load_fdf_schema(locale=None):
    """Load the FDF schema with sidecar JSON translations for the active locale."""
    schema = _load_raw_fdf_schema()
    resolved_locale = _resolve_locale(locale)
    if resolved_locale == "en":
        return schema

    translations = load_schema_i18n_catalog(resolved_locale)
    if not translations:
        return schema
    return apply_schema_i18n(schema, translations)
