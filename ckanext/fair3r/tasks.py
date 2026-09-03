"""
Update the FDF schema from the remote repository (or a local clone in DEV).

On validation / integration / production, ``fair3r update-schema`` downloads
the latest FDF schema from GitHub and writes it to the extension schema
directory. In DEV, when ``ckanext.fair3r.fdf_schema_dir`` points at a local
clone of fair3r-fdf-schema, the download is skipped and that clone is used
as-is.

Usage:
    ckan -c /path/to/ckan.ini fair3r update-schema
"""

import json
import logging
import os
import tempfile

import requests

from ckanext.fair3r.lib.utils import resolve_schema_dir

log = logging.getLogger(__name__)

REMOTE_BASE = "https://raw.githubusercontent.com/Phen-ICS/fair3r-fdf-schema/main"
REMOTE_URL = f"{REMOTE_BASE}/fdf_schema.json"
SUPPORTED_SCHEMA_LOCALES = ("fr",)
SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schema")
SCHEMA_PATH = os.path.join(SCHEMA_DIR, "fdf_schema.json")
I18N_DIR = os.path.join(SCHEMA_DIR, "i18n")


def _remote_schema_i18n_url(locale: str) -> str:
    return f"{REMOTE_BASE}/i18n/{locale}.json"


def _atomic_write_json(path, payload):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.rename(tmp_path, path)
        os.chmod(path, 0o644)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _download_json(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def _update_schema_i18n_sidecars(result, version):
    updated = []
    skipped = []
    for locale in SUPPORTED_SCHEMA_LOCALES:
        destination = os.path.join(I18N_DIR, f"{locale}.json")
        try:
            payload = _download_json(_remote_schema_i18n_url(locale))
        except requests.RequestException as exc:
            skipped.append(f"{locale} ({exc})")
            log.warning(
                "Schema i18n update skipped for %s: %s", locale, exc, exc_info=True
            )
            continue

        strings = payload.get("strings")
        if not isinstance(strings, dict):
            log.error("Invalid schema i18n sidecar for %s (missing strings)", locale)
            continue

        try:
            _atomic_write_json(destination, payload)
        except OSError as exc:
            log.error("Failed to write schema i18n sidecar %s: %s", destination, exc)
            continue

        updated.append(locale)

    parts = [f"Schema updated successfully (version: {version})"]
    if updated:
        parts.append(f"i18n updated: {', '.join(updated)}")
    if skipped:
        parts.append(f"i18n kept local: {', '.join(skipped)}")
    result["message"] = "; ".join(parts)


def update_fdf_schema():
    """Download and save the FDF schema from the remote repository.

    When a local schema clone is configured (DEV), skip the GitHub download
    so a container restart cannot overwrite in-progress schema work.

    Returns a dict with status information:
        - success: bool
        - message: str
        - version: str | None
    """
    result = {"success": False, "message": "", "version": None}

    schema_dir = resolve_schema_dir()
    if os.path.abspath(schema_dir) != os.path.abspath(SCHEMA_DIR):
        schema_path = os.path.join(schema_dir, "fdf_schema.json")
        try:
            with open(schema_path, "r", encoding="utf-8") as handle:
                schema = json.load(handle)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            result["message"] = f"Failed to read local schema at {schema_path}: {exc}"
            log.error("Schema update skipped (local clone): %s", exc)
            return result
        if isinstance(schema, dict):
            version = schema.get("version", "unknown")
        else:
            version = "unknown"
        result["success"] = True
        result["version"] = version
        result["message"] = (
            f"Using local FDF schema at {schema_dir} (version: {version}); "
            "GitHub download skipped"
        )
        log.info(result["message"])
        return result

    try:
        schema = _download_json(REMOTE_URL)
    except requests.RequestException as exc:
        result["message"] = f"Failed to fetch schema from GitHub: {exc}"
        log.error("Schema update failed: %s", exc)
        return result
    except (json.JSONDecodeError, ValueError) as exc:
        result["message"] = f"Invalid JSON from remote: {exc}"
        log.error("Schema update failed: %s", exc)
        return result

    version = schema.get("version", "unknown")
    result["version"] = version

    try:
        _atomic_write_json(SCHEMA_PATH, schema)
    except OSError as exc:
        result["message"] = f"Failed to write schema file: {exc}"
        log.error("Schema update failed: %s", exc)
        return result

    _update_schema_i18n_sidecars(result, version)

    result["success"] = True
    log.info("Schema updated successfully (version: %s)", version)
    return result
