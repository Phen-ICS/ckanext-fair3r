"""A dataset's FDF answers as (label, values) lines, labelled the way the
FDF schema's own display_mapping labels them - no subject scheme or field
name in code, so a new ontology or section needs a schema change only.

Used for the DataCite "Methods" description (datacite_converter.py) and by
ckanext-zenodo for the Zenodo record's description.
"""

import re


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _scheme_matches(scheme, wanted):
    if isinstance(wanted, str) and wanted.startswith("^"):
        return bool(re.match(wanted, scheme))
    return scheme == wanted


def _option_labels(section, path):
    """{value: label} of the choice fields writing to `path`."""
    labels = {}
    for field in section.get("fields") or []:
        if (field.get("output") or {}).get("path") == path:
            for option in field.get("options") or []:
                if isinstance(option, dict) and "value" in option:
                    labels[option["value"]] = option.get("label") or option["value"]
    return labels


def summary_lines(schema, fdf_data, subjects_only=False):
    """[(label, [values])] in schema order. A subject goes under its
    section's `display_mapping.labels[scheme]`, else the section title;
    other answers under `labels[key]`, else the section title, with choice
    values shown by their option label. Cross-references (`crossRefOf`)
    repeat their primary subject and are left out. Subjects no section
    claims (an older scheme, or no schema at all) go under their own
    scheme name, so nothing entered is dropped. `subjects_only`: leave
    out the answers that aren't subjects (publication year, publisher...)."""
    lines = {}

    def add(label, value):
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return
        text = str(value).strip()
        # Subjects saved before schema 3.0.4 carry their label as a prefix.
        if text.lower().startswith(label.lower() + ":"):
            text = text[len(label) + 1 :].strip()
        if not text:
            return
        values = lines.setdefault(label, [])
        if text.lower() not in (v.lower() for v in values):
            values.append(text)

    if not isinstance(fdf_data, dict):
        return []
    subjects = [
        s
        for s in _as_list(fdf_data.get("subjects"))
        if isinstance(s, dict) and not s.get("crossRefOf")
    ]
    claimed = set()

    for section in (schema or {}).get("sections") or []:
        mapping = section.get("display_mapping") or {}
        labels = mapping.get("labels") or {}
        title = section.get("title") or section.get("id") or ""
        for source in _as_list(mapping.get("source")):
            if source == "subjects":
                for wanted in _as_list(
                    (mapping.get("filter") or {}).get("subjectScheme")
                ):
                    for index, subject in enumerate(subjects):
                        scheme = str(subject.get("subjectScheme") or "")
                        if _scheme_matches(scheme, wanted):
                            claimed.add(index)
                            add(labels.get(scheme) or title, subject.get("subject"))
            elif isinstance(source, str) and not subjects_only:
                options = _option_labels(section, source)
                for value in _as_list(fdf_data.get(source)):
                    if isinstance(value, (str, int)) and value in options:
                        value = options[value]
                    add(labels.get(source) or title, value)

    for index, subject in enumerate(subjects):
        if index not in claimed:
            scheme = str(subject.get("subjectScheme") or "").strip() or "Subject"
            add(scheme, subject.get("subject"))

    return list(lines.items())
