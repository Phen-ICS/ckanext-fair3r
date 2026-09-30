"""
Shared helpers for reading FDF-derived "datacite.*" package extras from
custom RDF profiles (see croissant_profile.py and dcat_ap_profile.py).
"""

import json
import logging

log = logging.getLogger(__name__)


def get_extra(dataset_dict, key):
    for extra in dataset_dict.get("extras", []) or []:
        if isinstance(extra, dict) and extra.get("key") == key:
            return extra.get("value")
    return None


def get_json_extra(dataset_dict, key):
    raw = get_extra(dataset_dict, key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        log.warning("Could not parse extra '%s' as JSON for RDF output", key)
        return None
