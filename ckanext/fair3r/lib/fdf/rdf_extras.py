"""
Shared helpers for reading FDF-derived "datacite.*" package extras from
custom RDF profiles (see croissant_profile.py and dcat_ap_profile.py).
"""

import json
import logging
from urllib.parse import quote

from ckantoolkit import config

log = logging.getLogger(__name__)


def looks_like_uri(value):
    return isinstance(value, str) and value.startswith(("http://", "https://"))


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


def get_doi_url(dataset_dict):
    """Resolvable https://doi.org/... URL, only once ckanext-doi has
    actually published (registered) the DOI - a reserved-but-unpublished
    DOI is not a real, resolvable identifier yet."""
    if dataset_dict.get("doi") and dataset_dict.get("doi_status"):
        return f"https://doi.org/{dataset_dict['doi']}"
    return None


def subject_scheme_uri(scheme_name):
    """URI for a local, portal-scoped concept/term scheme minted from a FDF
    "subjectScheme" name (e.g. "NCBITaxon", "geneAccessionId"). FDF doesn't
    reliably provide a real, scheme-specific registry URI (its own
    "schemeURI" is often absent, and when present is the same generic OBO
    base shared by unrelated ontologies) - so rather than guess or omit the
    scheme entirely, mint one URI per scheme name under the portal's own
    namespace and label it, same as DCAT-AP recommends for catalog-defined
    vocabularies without an authoritative external one."""
    site_url = (config.get("ckan.site_url") or "").rstrip("/")
    return f"{site_url}/vocabulary/fdf-subject-scheme/{quote(scheme_name)}"
