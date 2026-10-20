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

Installed isn't enough: ckanext-zenodo can be installed without being
enabled (the Docker image ships every FAIR3R extension). Its table then
doesn't exist - querying it broke every dataset page with a 500 - and
its upload route isn't registered, so the Zenodo helpers also require
the plugin to be loaded, as fair3r already does for citations.
"""

import json
import logging

from ckan import plugins

log = logging.getLogger(__name__)


def fair3r_zenodo_routing_config():
    """Returns a JSON string, or None if ckanext-zenodo isn't enabled -
    the template guards the <meta> tag on this being truthy."""
    if not plugins.plugin_loaded("zenodo"):
        return None
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
    or None (ckanext-zenodo not enabled, or nothing published there)."""
    if not plugins.plugin_loaded("zenodo"):
        return None
    try:
        from ckanext.zenodo.lib.publish_guard import files_archive_url
    except ImportError:
        return None

    try:
        return files_archive_url(package_id)
    except Exception:
        log.exception("Failed to build the Zenodo files archive URL")
        return None


def fair3r_doi_url(doi):
    """ckanext-doi's own h.doi_resolver_url (DataCite's test resolver in
    test mode, doi.org in production), falling back to doi.org if that
    plugin/version isn't installed."""
    try:
        from ckanext.doi.lib.helpers import doi_resolver_url
    except ImportError:
        return f"https://doi.org/{doi}"
    return doi_resolver_url(doi)
