"""Tests for FDF schema sidecar i18n runtime loading."""

import json
from pathlib import Path

import pytest

from ckanext.fair3r.lib.fdf.schema import _load_raw_fdf_schema, load_fdf_schema
from ckanext.fair3r.lib.fdf.schema_i18n import (
    apply_schema_i18n,
    get_schema_i18n_path,
    load_schema_i18n_catalog,
)

FIXTURES = Path(__file__).parent / "fixtures"
FR_SIDECAR = FIXTURES / "fdf_i18n_fr.json"


@pytest.fixture
def raw_schema():
    return _load_raw_fdf_schema()


@pytest.fixture
def fr_translations():
    payload = json.loads(FR_SIDECAR.read_text(encoding="utf-8"))
    return payload["strings"]


def test_apply_schema_i18n_overlays_field_help(raw_schema, fr_translations):
    localized = apply_schema_i18n(raw_schema, fr_translations)
    field = localized["sections"][0]["fields"][0]
    assert field["help"] == (
        "Année de publication prévue ou effective du jeu de données"
    )


def test_apply_schema_i18n_falls_back_to_english(raw_schema):
    localized = apply_schema_i18n(raw_schema, {})
    field = localized["sections"][0]["fields"][0]
    assert field["help"] == "Year when the dataset will be or was published"


def test_load_fdf_schema_english_is_unmodified(raw_schema):
    schema = load_fdf_schema(locale="en")
    assert (
        schema["sections"][0]["fields"][0]["help"]
        == raw_schema["sections"][0]["fields"][0]["help"]
    )


def test_load_fdf_schema_french_translates_help(monkeypatch, fr_translations):
    monkeypatch.setattr(
        "ckanext.fair3r.lib.fdf.schema.load_schema_i18n_catalog",
        lambda locale: fr_translations if locale == "fr" else {},
    )
    monkeypatch.setattr("ckan.lib.i18n.get_lang", lambda: "fr")
    schema = load_fdf_schema()
    field = schema["sections"][0]["fields"][0]
    assert field["help"] == (
        "Année de publication prévue ou effective du jeu de données"
    )


def test_load_schema_i18n_catalog_unknown_locale():
    assert load_schema_i18n_catalog("zz") == {}


def test_downloaded_sidecar_path():
    assert get_schema_i18n_path("fr").endswith("schema/i18n/fr.json")
