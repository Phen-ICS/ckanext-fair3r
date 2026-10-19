"""Exposes ckanext-zenodo's routing_config_dict() (if that plugin is
installed) to base.html, as a JSON string for a <meta> tag that
resource-upload.js reads client-side to decide whether a file belongs on
Zenodo instead of CKAN storage.

A direct try/except ImportError, not h.zenodo_routing_config_json(): CKAN
has no h.helper_available(...) to safely check from a template whether
another, possibly-unloaded plugin's helper exists before calling it - the
established workaround in this codebase (see fair3r_completeness / its
own try/except around ckanext.citations' completeness_for_package) is for
the *calling* plugin to attempt the import itself and degrade gracefully.
"""

import json
import logging

log = logging.getLogger(__name__)


def fair3r_zenodo_routing_config():
    """Returns a JSON string, or None if ckanext-zenodo isn't installed -
    the template guards the <meta> tag on this being truthy."""
    try:
        from ckanext.zenodo.lib.zenodo_config import routing_config_dict
    except ImportError:
        return None

    try:
        return json.dumps(routing_config_dict())
    except Exception:
        log.exception("Failed to build the Zenodo routing config for the page")
        return None


def fair3r_zenodo_files_archive_url(package_id):
    """URL of Zenodo's own ZIP of this dataset's published Zenodo files,
    or None (ckanext-zenodo not installed, or nothing published there)."""
    try:
        from ckanext.zenodo.lib.publish_guard import files_archive_url
    except ImportError:
        return None

    try:
        return files_archive_url(package_id)
    except Exception:
        log.exception("Failed to build the Zenodo files archive URL")
        return None
