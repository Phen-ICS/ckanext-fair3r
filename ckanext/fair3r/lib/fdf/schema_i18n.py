"""
Sidecar JSON internationalization for the FDF schema (runtime only).

Translations are maintained in the fair3r-fdf-schema repository (i18n/<locale>.json)
and downloaded by ``fair3r update-schema``. Key paths must stay aligned with
``tools/i18n.py`` in that repository.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re

log = logging.getLogger(__name__)

LOCALIZABLE_KEYS = frozenset({"title", "label", "placeholder", "help_text", "help"})
SKIP_PREFIXES = ("{{", "{%")


def get_schema_i18n_dir() -> str:
    plugin_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(plugin_dir, "schema", "i18n")


def get_schema_i18n_path(locale: str) -> str:
    return os.path.join(get_schema_i18n_dir(), f"{locale}.json")


def _is_translatable_string(value) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    return not stripped.startswith(SKIP_PREFIXES)


def _safe_key_part(value, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if text.startswith("http://") or text.startswith("https://"):
        text = text.rstrip("/").rsplit("/", 1)[-1]
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text)
    return text or fallback


def _option_key(option: dict, index: int) -> str:
    for candidate in ("id", "value", "name"):
        if candidate in option:
            return _safe_key_part(option.get(candidate), str(index))
    return str(index)


def _translate_string(value, key: str, translations: dict) -> str:
    if not _is_translatable_string(value):
        return value
    translated = translations.get(key)
    if isinstance(translated, str) and translated.strip():
        return translated
    return value


def apply_schema_i18n(schema: dict, translations: dict) -> dict:
    """Return a deep copy of *schema* with sidecar translations applied."""
    if not translations:
        return schema

    localized = copy.deepcopy(schema)

    meta = localized.get("meta")
    if isinstance(meta, dict) and "title" in meta:
        meta["title"] = _translate_string(meta.get("title"), "meta.title", translations)

    apis = localized.get("apis")
    if isinstance(apis, dict):
        for api_name, api in apis.items():
            if isinstance(api, dict) and "label" in api:
                api["label"] = _translate_string(
                    api.get("label"), f"apis.{api_name}.label", translations
                )

    vocabularies = localized.get("vocabularies")
    if isinstance(vocabularies, dict):
        for vocab_name, vocab in vocabularies.items():
            if not isinstance(vocab, dict):
                continue
            if "label" in vocab:
                vocab["label"] = _translate_string(
                    vocab.get("label"),
                    f"vocabularies.{vocab_name}.label",
                    translations,
                )
            for index, item in enumerate(vocab.get("items", []) or []):
                if not isinstance(item, dict):
                    continue
                item_key = _option_key(item, index)
                prefix = f"vocabularies.{vocab_name}.items.{item_key}"
                for prop in ("label", "display"):
                    if prop in item:
                        item[prop] = _translate_string(
                            item.get(prop), f"{prefix}.{prop}", translations
                        )

    for section_index, section in enumerate(localized.get("sections", []) or []):
        if not isinstance(section, dict):
            continue
        section_id = _safe_key_part(section.get("id"), str(section_index))
        section_prefix = f"sections.{section_id}"

        if "title" in section:
            section["title"] = _translate_string(
                section.get("title"), f"{section_prefix}.title", translations
            )

        display_mapping = section.get("display_mapping")
        if isinstance(display_mapping, dict):
            labels = display_mapping.get("labels")
            if isinstance(labels, dict):
                for label_key, label in list(labels.items()):
                    safe_label_key = _safe_key_part(label_key, label_key)
                    labels[label_key] = _translate_string(
                        label,
                        f"{section_prefix}.display_mapping.labels.{safe_label_key}",
                        translations,
                    )

        for field_index, field in enumerate(section.get("fields", []) or []):
            if not isinstance(field, dict):
                continue
            field_id = _safe_key_part(field.get("id"), str(field_index))
            field_prefix = f"{section_prefix}.fields.{field_id}"
            for key in LOCALIZABLE_KEYS:
                if key in field:
                    field[key] = _translate_string(
                        field.get(key), f"{field_prefix}.{key}", translations
                    )
            for option_index, option in enumerate(field.get("options", []) or []):
                if isinstance(option, dict) and "label" in option:
                    option_key = _option_key(option, option_index)
                    option["label"] = _translate_string(
                        option.get("label"),
                        f"{field_prefix}.options.{option_key}.label",
                        translations,
                    )

    return localized


def load_schema_i18n_catalog(locale: str) -> dict:
    """Load the ``strings`` mapping from the downloaded sidecar for *locale*."""
    path = get_schema_i18n_path(locale)
    if not os.path.isfile(path):
        log.debug("No FDF schema i18n sidecar for locale %s at %s", locale, path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as err:
        log.error("Failed to load FDF schema i18n sidecar %s: %s", path, err)
        return {}
    strings = payload.get("strings")
    if not isinstance(strings, dict):
        log.error("Invalid FDF schema i18n sidecar (missing strings dict): %s", path)
        return {}
    return strings
