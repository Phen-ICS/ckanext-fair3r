"""
Celery background task to update the FDF schema from the remote repository.

This module defines a Celery task that downloads the latest FDF schema from
GitHub, validates it, and writes it to the local schema directory.

Usage in dev:
    ckan -c /path/to/dev.ini fair3r update-schema

The CLI command triggers this task asynchronously via Celery.
"""

import json
import logging
import os
import tempfile

import requests

log = logging.getLogger(__name__)

REMOTE_URL = (
    "https://raw.githubusercontent.com/Phen-ICS/fair3r-fdf-schema/main/fdf_schema.json"
)
SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schema")
SCHEMA_PATH = os.path.join(SCHEMA_DIR, "fdf_schema.json")


def update_fdf_schema():
    """Download and save the FDF schema from the remote repository.

    Returns a dict with status information:
        - success: bool
        - message: str
        - version: str | None
    """
    result = {"success": False, "message": "", "version": None}

    try:
        response = requests.get(REMOTE_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        result["message"] = f"Failed to fetch schema from GitHub: {exc}"
        log.error("Schema update failed: %s", exc)
        return result

    # Validate JSON before writing
    try:
        schema = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        result["message"] = f"Invalid JSON from remote: {exc}"
        log.error("Schema update failed: %s", exc)
        return result

    # Extract version if present
    version = schema.get("version", "unknown")
    result["version"] = version

    # Ensure the schema directory exists
    os.makedirs(SCHEMA_DIR, exist_ok=True)

    # Atomic write: write to a temp file first, then rename
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=SCHEMA_DIR, prefix="fdf_schema_", suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.rename(tmp_path, SCHEMA_PATH)
        # Ensure the file is readable by all users (fixes permission issues)
        os.chmod(SCHEMA_PATH, 0o644)
    except OSError as exc:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        result["message"] = f"Failed to write schema file: {exc}"
        log.error("Schema update failed: %s", exc)
        return result

    result["success"] = True
    result["message"] = f"Schema updated successfully (version: {version})"
    log.info("Schema updated successfully (version: %s)", version)
    return result
