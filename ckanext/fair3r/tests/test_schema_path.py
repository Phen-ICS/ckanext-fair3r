"""Tests for FDF schema directory resolution (local clone vs bundled)."""

import json
import os

from ckanext.fair3r.lib import utils
from ckanext.fair3r.lib.fdf.schema_i18n import get_schema_i18n_path
from ckanext.fair3r.lib.utils import get_schema_json_path, resolve_schema_dir
from ckanext.fair3r.tasks import SCHEMA_DIR, update_fdf_schema


def _bundled_schema_dir():
    plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(utils.__file__)))
    return os.path.join(plugin_dir, "schema")


def test_resolve_schema_dir_defaults_to_bundled(monkeypatch):
    monkeypatch.delenv("CKANEXT_FAIR3R_FDF_SCHEMA_DIR", raising=False)
    assert resolve_schema_dir() == _bundled_schema_dir()
    assert get_schema_json_path().endswith("schema/fdf_schema.json")
    assert os.path.abspath(resolve_schema_dir()) == os.path.abspath(SCHEMA_DIR)


def test_resolve_schema_dir_uses_configured_clone(tmp_path, monkeypatch):
    schema_file = tmp_path / "fdf_schema.json"
    schema_file.write_text("{}", encoding="utf-8")
    (tmp_path / "i18n").mkdir()
    monkeypatch.setenv("CKANEXT_FAIR3R_FDF_SCHEMA_DIR", str(tmp_path))
    assert resolve_schema_dir() == str(tmp_path)
    assert get_schema_json_path() == str(schema_file)
    assert get_schema_i18n_path("fr") == str(tmp_path / "i18n" / "fr.json")
    assert os.path.abspath(resolve_schema_dir()) != os.path.abspath(SCHEMA_DIR)


def test_resolve_schema_dir_falls_back_if_configured_dir_has_no_schema(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CKANEXT_FAIR3R_FDF_SCHEMA_DIR", str(tmp_path))
    assert resolve_schema_dir() == _bundled_schema_dir()
    assert os.path.abspath(resolve_schema_dir()) == os.path.abspath(SCHEMA_DIR)


def test_update_fdf_schema_skips_github_for_local_clone(tmp_path, monkeypatch):
    payload = {"version": "9.9.9", "sections": []}
    (tmp_path / "fdf_schema.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        "ckanext.fair3r.tasks.resolve_schema_dir", lambda: str(tmp_path)
    )
    called = []
    monkeypatch.setattr(
        "ckanext.fair3r.tasks._download_json",
        lambda url: called.append(url) or payload,
    )

    result = update_fdf_schema()

    assert result["success"] is True
    assert result["version"] == "9.9.9"
    assert "GitHub download skipped" in result["message"]
    assert str(tmp_path) in result["message"]
    assert called == []
