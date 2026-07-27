"""
FDF values validation.
"""

import json
import logging
import re

from ckan.plugins import toolkit

log = logging.getLogger(__name__)


def _(text):
    """Translate user-facing text, falling back to the English msgid when no
    request/app context is available (e.g. direct calls from tests or CLI)."""
    try:
        return toolkit._(text)
    except KeyError:
        return text


def _get_nested(data, path, default=None):
    if not path:
        return default
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _extract_values_from_array_entry(entry):
    if isinstance(entry, dict):
        return [v for v in entry.values() if isinstance(v, str)]
    if isinstance(entry, str):
        return [entry]
    return []


def _build_field_by_id(section):
    fields = section.get("fields", []) or []
    return {f.get("id"): f for f in fields if isinstance(f, dict) and f.get("id")}


def _get_field_output_value(field, fdf_data):
    output = field.get("output") or {}
    path = output.get("path")
    if not path:
        return None
    return _get_nested(fdf_data, path)


def _get_condition_controller_value(section, controller_id, fdf_data, item=None):
    """Resolve controller value for condition/visible_if checks.

    Priority for collect_object sections:
    1) current item via controller field obj_key
    2) fallback to full output path value
    """
    if not controller_id:
        return None

    fields_by_id = _build_field_by_id(section)
    controller_field = fields_by_id.get(controller_id)

    if item is not None and isinstance(controller_field, dict):
        output = controller_field.get("output") or {}
        obj_key = output.get("obj_key")
        if obj_key and isinstance(item, dict):
            return item.get(obj_key)

    if isinstance(controller_field, dict):
        value = _get_field_output_value(controller_field, fdf_data)
        if value is not None:
            return value

    return _get_nested(fdf_data, controller_id)


def _resolve_field_id_value(schema, field_id, fdf_data):
    """Resolve a schema field id to its persisted output value in fdf_data when possible."""
    if not field_id:
        return None

    for section in schema.get("sections", []) or []:
        for field in section.get("fields", []) or []:
            if not isinstance(field, dict) or field.get("id") != field_id:
                continue

            output = field.get("output") or {}
            path = output.get("path")
            if path:
                return _get_nested(fdf_data, path)

            return _get_nested(fdf_data, field_id)

    return _get_nested(fdf_data, field_id)


def _is_section_active(schema, section, fdf_data):
    condition = section.get("condition") or {}
    if not condition:
        return True

    condition_type = condition.get("type")
    field_id = condition.get("field_id")
    expected = condition.get("value")
    current = _resolve_field_id_value(schema, field_id, fdf_data)

    if condition_type == "checkbox_includes":
        return isinstance(current, list) and expected in current

    if condition_type in ("equals", "equal"):
        return current == expected

    if condition_type == "organism_trigger":
        trigger = condition.get("trigger")
        if not trigger:
            return True

        subjects = _get_nested(fdf_data, "subjects", [])
        if not isinstance(subjects, list):
            return False

        organism_uri = ""
        for item in subjects:
            if not isinstance(item, dict):
                continue
            if item.get("subjectScheme") == "NCBITaxon":
                organism_uri = item.get("valueURI") or item.get("id") or ""
                if organism_uri:
                    break

        if not organism_uri:
            return False

        presets = (
            ((schema or {}).get("vocabularies") or {}).get("organism_presets") or {}
        ).get("items") or []
        preset = next(
            (
                item
                for item in presets
                if isinstance(item, dict) and item.get("id") == organism_uri
            ),
            None,
        )
        if not preset:
            return False

        triggers = preset.get("triggers") or []
        return isinstance(triggers, list) and trigger in triggers

    return True


def _is_field_visible_in_context(field, section, fdf_data, item=None):
    rule = field.get("visible_if") or {}
    if not rule:
        return True

    controller = rule.get("field")
    expected = rule.get("value")
    actual = _get_condition_controller_value(section, controller, fdf_data, item)
    return actual == expected


def _field_output_has_value(field, section, fdf_data):
    output = field.get("output") or {}
    path = output.get("path")
    mode = output.get("mode", "set")

    if not path:
        return False

    value = _get_nested(fdf_data, path)

    if mode in ("set", "set_int"):
        return not _is_empty(value)

    if mode in ("append", "append_if", "wrap_array", "append_from_array"):
        if not isinstance(value, list) or not value:
            return False

        subject_scheme = section.get("subject_scheme")
        # Apply subjectScheme filtering only for subjects[] payloads.
        # Other append arrays (e.g. treatmentProtocol) store plain strings.
        if subject_scheme and path == "subjects":
            for item in value:
                if (
                    isinstance(item, dict)
                    and item.get("subjectScheme") == subject_scheme
                    and not _is_empty(item.get("subject"))
                ):
                    return True
            return False

        for item in value:
            if not _is_empty(item):
                return True
        return False

    return not _is_empty(value)


def _section_min_instances(section):
    """Minimum number of required instances for a repeatable section.
    - initial_instances == 0 means the section is optional (min 0)
    """
    initial_instances = section.get("initial_instances")
    if isinstance(initial_instances, (int, float)) and initial_instances == 0:
        return 0
    return 1


def _validate_required_fields(schema, fdf_data):
    errors = {}

    for section in schema.get("sections", []):
        if not _is_section_active(schema, section, fdf_data):
            continue

        fields = section.get("fields", [])
        required_fields = [f for f in fields if f.get("required")]
        if not required_fields:
            continue

        section_output = section.get("output") or {}
        if section_output.get("mode") == "collect_object" and section_output.get(
            "path"
        ):
            items = _get_nested(fdf_data, section_output.get("path"), [])
            if not isinstance(items, list) or len(items) == 0:
                # Skip the "at least one entry" requirement when nothing was entered.
                if _section_min_instances(section) == 0:
                    continue
                section_title = section.get("title", section.get("id", "section"))
                errors.setdefault(section_title, []).append(
                    _("At least one entry is required.")
                )
                continue

            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                for field in required_fields:
                    if not _is_field_visible_in_context(field, section, fdf_data, item):
                        continue

                    output = field.get("output") or {}
                    obj_key = output.get("obj_key")
                    if not obj_key:
                        continue
                    if _is_empty(item.get(obj_key)):
                        field_label = field.get("label", field.get("id", "field"))
                        key = f"{section.get('title', section.get('id', 'section'))} [{idx + 1}]"
                        errors.setdefault(key, []).append(
                            _("%(field)s: required field.") % {"field": field_label}
                        )
            continue

        for field in required_fields:
            if not _is_field_visible_in_context(field, section, fdf_data):
                continue

            if not _field_output_has_value(field, section, fdf_data):
                field_label = field.get("label", field.get("id", "field"))
                section_title = section.get("title", section.get("id", "section"))
                errors.setdefault(section_title, []).append(
                    _("%(field)s: required field.") % {"field": field_label}
                )

    return errors


def _validate_vocabularies(schema, fdf_data):
    errors = {}
    vocabularies = schema.get("vocabularies", {})

    for section in schema.get("sections", []):
        for field in section.get("fields", []):
            output = field.get("output") or {}
            path = output.get("path")
            if not path:
                continue

            field_type = field.get("type")
            label = field.get("label", field.get("id", "field"))
            section_title = section.get("title", section.get("id", "section"))
            mode = output.get("mode", "set")

            # Skip validation for select fields with append_if mode as they share paths with other fields
            if field_type == "select" and mode != "append_if":
                allowed = {
                    opt.get("value")
                    for opt in field.get("options", [])
                    if opt.get("value") is not None
                }
                raw_value = _get_nested(fdf_data, path)
                if isinstance(raw_value, list):
                    present = []
                    for item in raw_value:
                        present.extend(_extract_values_from_array_entry(item))
                    if present and not any(v in allowed for v in present):
                        errors.setdefault(section_title, []).append(
                            _(
                                "%(field)s: value does not match allowed vocabulary/options."
                            )
                            % {"field": label}
                        )

            if field_type == "multi_select" and field.get("vocabulary"):
                vocab = vocabularies.get(field.get("vocabulary"), {})
                allowed = {
                    item.get("id") for item in vocab.get("items", []) if item.get("id")
                }
                entries = _get_nested(fdf_data, path, [])
                if isinstance(entries, list):
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        roles = entry.get("contributorRoles", [])
                        for role in roles:
                            role_uri = (
                                role.get("contributorRoleURI")
                                if isinstance(role, dict)
                                else None
                            )
                            if role_uri and role_uri not in allowed:
                                errors.setdefault(section_title, []).append(
                                    _(
                                        "%(field)s: value '%(value)s' is outside allowed vocabulary."
                                    )
                                    % {"field": label, "value": role_uri}
                                )

            if field_type == "checkbox_group" and field.get("options"):
                allowed = {
                    opt.get("value")
                    for opt in field.get("options", [])
                    if opt.get("value") is not None
                }
                values = _get_nested(fdf_data, path)
                if isinstance(values, list):
                    invalid = [v for v in values if v not in allowed]
                    if invalid:
                        errors.setdefault(section_title, []).append(
                            _("%(field)s: invalid option(s): %(values)s.")
                            % {
                                "field": label,
                                "values": ", ".join(str(v) for v in invalid),
                            }
                        )

    return errors


def _validate_pattern_fields(schema, fdf_data):
    errors = {}

    for section in schema.get("sections", []):
        fields = section.get("fields", [])

        section_output = section.get("output") or {}
        if section_output.get("mode") == "collect_object" and section_output.get(
            "path"
        ):
            items = _get_nested(fdf_data, section_output.get("path"), [])
            if isinstance(items, list):
                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        continue
                    for field in fields:
                        pattern = field.get("pattern")
                        if not pattern:
                            continue

                        output = field.get("output") or {}
                        obj_key = output.get("obj_key")
                        if not obj_key:
                            continue

                        value = item.get(obj_key)
                        if _is_empty(value):
                            continue

                        try:
                            if not re.match(pattern, str(value)):
                                field_label = field.get(
                                    "label", field.get("id", "field")
                                )
                                section_title = section.get(
                                    "title", section.get("id", "section")
                                )
                                key = f"{section_title} [{idx + 1}]"
                                errors.setdefault(key, []).append(
                                    _("%(field)s: invalid format.")
                                    % {"field": field_label}
                                )
                        except re.error as exc:
                            log.warning(
                                "Invalid regex pattern in schema field '%s': %s",
                                field.get("id"),
                                exc,
                            )

        for field in fields:
            pattern = field.get("pattern")
            if not pattern:
                continue

            output = field.get("output") or {}
            path = output.get("path")
            if not path:
                continue

            value = _get_nested(fdf_data, path)
            if _is_empty(value):
                continue

            try:
                if not re.match(pattern, str(value)):
                    field_label = field.get("label", field.get("id", "field"))
                    section_title = section.get("title", section.get("id", "section"))
                    errors.setdefault(section_title, []).append(
                        _("%(field)s: invalid format.") % {"field": field_label}
                    )
            except re.error as exc:
                log.warning(
                    "Invalid regex pattern in schema field '%s': %s",
                    field.get("id"),
                    exc,
                )

    return errors


def _validate_duplicate_people(fdf_data):
    errors = {}
    section_title = _("Authors & Contributors")

    # Creators and Contributors are independent: duplicates inside each list are
    # rejected, but a person may legitimately appear in both lists.
    creators = fdf_data.get("creators", [])
    if isinstance(creators, list):
        seen_creators = set()
        for idx, creator in enumerate(creators):
            if not isinstance(creator, dict):
                continue
            key = (
                str(creator.get("givenName") or "").strip().lower(),
                str(creator.get("familyName") or "").strip().lower(),
                str(creator.get("email") or "").strip().lower(),
            )
            if not any(key):
                continue
            if key in seen_creators:
                errors.setdefault(section_title, []).append(
                    _("Duplicate author/maintainer entry at item #%(num)s.")
                    % {"num": idx + 1}
                )
            else:
                seen_creators.add(key)

    contributors = fdf_data.get("contributors", [])
    if isinstance(contributors, list):
        seen_contributors = set()
        for idx, contributor in enumerate(contributors):
            if not isinstance(contributor, dict):
                continue

            roles = contributor.get("contributorRoles", [])
            role_values = []
            if isinstance(roles, list):
                for role in roles:
                    if isinstance(role, dict):
                        role_value = role.get("contributorRoleURI") or role.get(
                            "contributorRole"
                        )
                        if role_value:
                            role_values.append(str(role_value).strip().lower())

            key = (
                str(contributor.get("name") or "").strip().lower(),
                str(contributor.get("contributorType") or "").strip().lower(),
                tuple(sorted(role_values)),
            )
            if not (key[0] or key[1] or key[2]):
                continue
            if key in seen_contributors:
                errors.setdefault(section_title, []).append(
                    _("Duplicate contributor entry at item #%(num)s.")
                    % {"num": idx + 1}
                )
            else:
                seen_contributors.add(key)

    return errors


def _extract_controlled_subject_rules(schema):
    """Build validation rules for subjects[] entries from schema definitions."""
    rules = []

    for section in schema.get("sections", []):
        section_title = section.get("title", section.get("id", "Section"))
        for field in section.get("fields", []):
            output = field.get("output") or {}
            if output.get("path") != "subjects":
                continue

            tpl = output.get("tpl") or {}
            if not isinstance(tpl, dict):
                continue

            field_label = field.get("label", field.get("id", "field"))
            field_title = f"{section_title} / {field_label}"

            subject_tpl = tpl.get("subject")
            subject_prefix = None
            if isinstance(subject_tpl, str):
                if "$" in subject_tpl:
                    subject_prefix = subject_tpl.split("$", 1)[0]
                else:
                    subject_prefix = subject_tpl

            scheme_tpl = tpl.get("subjectScheme")
            scheme_value = None
            if isinstance(scheme_tpl, str):
                if scheme_tpl == "$scheme":
                    api_key = field.get("api") or field.get("search_api")
                    scheme_value = _get_nested(schema, f"apis.{api_key}.mapper.scheme")
                elif not scheme_tpl.startswith("$"):
                    scheme_value = scheme_tpl

            require_value_uri = "valueURI" in tpl
            require_http_uri = False
            if require_value_uri:
                value_uri_tpl = tpl.get("valueURI")
                if isinstance(value_uri_tpl, str):
                    if value_uri_tpl.startswith(("http://", "https://")):
                        require_http_uri = True
                    elif value_uri_tpl in ("$id", "$value"):
                        api_key = field.get("api") or field.get("search_api")
                        mapper_id = _get_nested(schema, f"apis.{api_key}.mapper.id")
                        if isinstance(mapper_id, str) and mapper_id.startswith(
                            ("http://", "https://")
                        ):
                            require_http_uri = True

            rules.append(
                {
                    "field_title": field_title,
                    "scheme": scheme_value,
                    "subject_prefix": subject_prefix,
                    "require_value_uri": require_value_uri,
                    "require_http_uri": require_http_uri,
                }
            )

    return rules


def _subject_matches_rule(subject, rule):
    if not isinstance(subject, dict):
        return False

    scheme = str(subject.get("subjectScheme") or "").strip()
    label = str(subject.get("subject") or "").strip()

    rule_scheme = (rule.get("scheme") or "").strip()
    rule_prefix = rule.get("subject_prefix")

    if rule_scheme and scheme != rule_scheme:
        return False

    if (
        isinstance(rule_prefix, str)
        and rule_prefix
        and not label.startswith(rule_prefix)
    ):
        return False

    return bool(rule_scheme or (isinstance(rule_prefix, str) and rule_prefix))


def _validate_controlled_subjects(schema, fdf_data):
    """
    Validate controlled-vocabulary subjects structure.

    Protects against cases where users type arbitrary text in API-backed fields
    without selecting a result, producing malformed valueURI/subjectScheme pairs.
    """
    errors = {}
    section_title = _("FAIR Metadata (FDF)")

    subjects = fdf_data.get("subjects", [])
    if not isinstance(subjects, list):
        return errors

    rules = _extract_controlled_subject_rules(schema)
    if not rules:
        return errors

    seen_messages = set()

    for rule in rules:
        matching_subjects = [s for s in subjects if _subject_matches_rule(s, rule)]
        if not matching_subjects:
            continue

        for subject in matching_subjects:
            label = str(subject.get("subject") or "").strip()
            value_uri = str(subject.get("valueURI") or "").strip()
            field_title = rule.get("field_title") or _("Controlled vocabulary field")

            if not label:
                msg = _("%(field)s: missing label for controlled vocabulary entry.") % {
                    "field": field_title
                }
                if msg not in seen_messages:
                    errors.setdefault(section_title, []).append(msg)
                    seen_messages.add(msg)

            if rule.get("require_value_uri") and not value_uri:
                msg = _(
                    "%(field)s: missing identifier URI (choose a value from vocabulary search results)."
                ) % {"field": field_title}
                if msg not in seen_messages:
                    errors.setdefault(section_title, []).append(msg)
                    seen_messages.add(msg)
                continue

            if (
                rule.get("require_http_uri")
                and value_uri
                and not value_uri.startswith(("http://", "https://"))
            ):
                msg = _("%(field)s: invalid identifier URI '%(uri)s'.") % {
                    "field": field_title,
                    "uri": value_uri,
                }
                if msg not in seen_messages:
                    errors.setdefault(section_title, []).append(msg)
                    seen_messages.add(msg)

    return errors


def merge_errors(*error_maps):
    merged = {}
    for err_map in error_maps:
        for key, messages in (err_map or {}).items():
            if not messages:
                continue
            merged.setdefault(key, []).extend(messages)
    return merged


def validate_fdf_output_json(raw_json, schema):
    if not isinstance(schema, dict):
        schema = {}

    if not raw_json or not str(raw_json).strip():
        return (
            {},
            {_("FAIR Metadata (FDF)"): [_("Missing FDF metadata payload.")]},
            {_("FAIR Metadata (FDF)"): _("Missing FDF metadata payload.")},
        )

    try:
        fdf_data = json.loads(raw_json)
    except (json.JSONDecodeError, ValueError, TypeError):
        return (
            {},
            {_("FAIR Metadata (FDF)"): [_("FDF payload is not valid JSON.")]},
            {_("FAIR Metadata (FDF)"): _("FDF payload is not valid JSON.")},
        )

    required_errors = _validate_required_fields(schema, fdf_data)
    vocab_errors = _validate_vocabularies(schema, fdf_data)
    pattern_errors = _validate_pattern_fields(schema, fdf_data)
    duplicate_errors = _validate_duplicate_people(fdf_data)
    controlled_subject_errors = _validate_controlled_subjects(schema, fdf_data)
    all_errors = merge_errors(
        required_errors,
        vocab_errors,
        pattern_errors,
        duplicate_errors,
        controlled_subject_errors,
    )

    error_summary = {}
    for key, messages in all_errors.items():
        if messages:
            error_summary[key] = messages[0]

    return fdf_data, all_errors, error_summary
