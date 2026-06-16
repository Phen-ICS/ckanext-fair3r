"""
FDF schema loading utilities.
"""

import json
import logging
from ckanext.fair3r.lib.utils import get_schema_json_path

log = logging.getLogger(__name__)


def load_fdf_schema():
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
