"""Completeness score of a FAIR3R dataset, for the colour gamification.

Only fields that are actually applicable count: a field inside a section
whose condition is false, or whose visible_if rule is false, is ignored
(same rules validation.py uses to decide what is required). Required fields
weigh more than optional ones, and the CKAN base fields count too.
"""

from ckanext.fair3r.lib.fdf.validation import (
    _field_output_has_value,
    _find_selected_organism_preset,
    _get_condition_controller_value,
    _get_nested,
    _is_empty,
    _is_section_active,
    _section_min_instances,
)

WEIGHT_REQUIRED = 2
WEIGHT_OPTIONAL = 1

BASE_FIELDS = (
    ("title", "Title", WEIGHT_REQUIRED),
    ("notes", "Description", WEIGHT_OPTIONAL),
    ("tags", "Tags", WEIGHT_OPTIONAL),
    ("license_id", "License", WEIGHT_OPTIONAL),
)

RED_BELOW = 50
GREEN_FROM = 80


def _field_filled(field, section, fdf_data):
    """A subject field is filled when a subject with its own subjectScheme exists.

    The generic check only looks at the section's scheme, so every field of a
    gene section looked filled as soon as one gene was present.
    """
    output = field.get("output") or {}
    scheme = (output.get("tpl") or {}).get("subjectScheme")
    if output.get("path") == "subjects" and scheme and not scheme.startswith("$"):
        subjects = _get_nested(fdf_data, "subjects", []) or []
        return any(
            isinstance(item, dict)
            and item.get("subjectScheme") == scheme
            and not _is_empty(item.get("subject"))
            for item in subjects
        )
    return _field_output_has_value(field, section, fdf_data)


def _is_field_applicable(schema, field, section, fdf_data, item=None):
    """visible_if rules as written in the FDF schema: {field, value},
    {field, not_empty[, taxon_in|taxon_not_in]}, {field, checked}."""
    rule = field.get("visible_if") or {}
    if not rule:
        return True

    actual = _get_condition_controller_value(section, rule.get("field"), fdf_data, item)

    if "checked" in rule:
        return bool(actual) == bool(rule["checked"])
    if "value" in rule:
        return actual == rule["value"]
    if rule.get("not_empty") and _is_empty(actual):
        return False

    if "taxon_in" in rule or "taxon_not_in" in rule:
        preset = _find_selected_organism_preset(schema, fdf_data) or {}
        taxon = str(preset.get("taxon_id") or "")
        if "taxon_in" in rule and taxon not in {str(t) for t in rule["taxon_in"]}:
            return False
        if "taxon_not_in" in rule and taxon in {str(t) for t in rule["taxon_not_in"]}:
            return False
    return True


def _base_field_value(pkg, key):
    value = pkg.get(key)
    return not _is_empty(value)


def _section_title(section):
    return section.get("title", section.get("id", "section"))


def _field_label(field):
    return field.get("label", field.get("id", "field"))


def _score_section(schema, section, fdf_data):
    """Return (filled_weight, total_weight, missing) for one active section."""
    filled = total = 0
    missing = []
    fields = section.get("fields", []) or []
    section_output = section.get("output") or {}
    is_collection = section_output.get(
        "mode"
    ) == "collect_object" and section_output.get("path")

    if is_collection:
        items = _get_nested(fdf_data, section_output.get("path"), [])
        if not isinstance(items, list) or not items:
            if _section_min_instances(section) >= 1:
                for field in fields:
                    if (
                        not field.get("required")
                        or field.get("type") == "checkbox_group"
                    ):
                        continue
                    weight = WEIGHT_REQUIRED
                    total += weight
                    missing.append((_section_title(section), _field_label(field), True))
            return filled, total, missing

        for item in items:
            if not isinstance(item, dict):
                continue
            for field in fields:
                if field.get("type") == "checkbox_group":
                    continue
                if not _is_field_applicable(schema, field, section, fdf_data, item):
                    continue
                obj_key = (field.get("output") or {}).get("obj_key")
                if not obj_key:
                    continue
                weight = WEIGHT_REQUIRED if field.get("required") else WEIGHT_OPTIONAL
                total += weight
                if _is_empty(item.get(obj_key)):
                    missing.append(
                        (
                            _section_title(section),
                            _field_label(field),
                            bool(field.get("required")),
                        )
                    )
                else:
                    filled += weight
        return filled, total, missing

    for field in fields:
        if field.get("type") == "checkbox_group":
            continue
        if not _is_field_applicable(schema, field, section, fdf_data):
            continue
        weight = WEIGHT_REQUIRED if field.get("required") else WEIGHT_OPTIONAL
        total += weight
        if _field_filled(field, section, fdf_data):
            filled += weight
        else:
            missing.append(
                (
                    _section_title(section),
                    _field_label(field),
                    bool(field.get("required")),
                )
            )
    return filled, total, missing


def compute_completeness(schema, fdf_data, pkg):
    """Return {"score": int 0-100, "band": "red"|"orange"|"green",
    "missing": [(section, label, required), ...]}.

    `pkg` is the CKAN package dict (for the base fields), `fdf_data` the parsed
    fdf_output_json, `schema` the loaded FDF schema.
    """
    filled = total = 0
    missing = []

    for key, label, weight in BASE_FIELDS:
        total += weight
        if _base_field_value(pkg, key):
            filled += weight
        else:
            missing.append(("CKAN", label, weight == WEIGHT_REQUIRED))

    for section in schema.get("sections", []) or []:
        if not _is_section_active(schema, section, fdf_data):
            continue
        s_filled, s_total, s_missing = _score_section(schema, section, fdf_data)
        filled += s_filled
        total += s_total
        missing.extend(s_missing)

    score = round(100 * filled / total) if total else 0
    if score >= GREEN_FROM:
        band = "green"
    elif score >= RED_BELOW:
        band = "orange"
    else:
        band = "red"
    return {"score": score, "band": band, "missing": missing}


def completeness_for_package(pkg_dict):
    """Completeness for a CKAN package dict, reading its fdf_output_json extra."""
    import json

    from ckanext.fair3r.lib.fdf.rdf_extras import get_extra
    from ckanext.fair3r.lib.fdf.schema import load_fdf_schema

    raw = get_extra(pkg_dict, "fdf_output_json")
    try:
        fdf_data = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        fdf_data = {}
    return compute_completeness(load_fdf_schema(), fdf_data, pkg_dict)
