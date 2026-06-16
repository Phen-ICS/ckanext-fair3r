"""
FDF tags utilities.
"""


def build_tags_payload_from_request(form, data_dict):
    """Build CKAN tags payload from possible form sources.
    Supports both `tag_string` and autocomplete-style `tags` inputs.
    Returns a tuple: (has_tag_input, tags_payload).
    """
    raw_parts = []
    has_tag_input = False
    if "tag_string" in form:
        has_tag_input = True
        raw_val = form.get("tag_string")
        if isinstance(raw_val, str):
            raw_parts.append(raw_val)
    if "tags" in form:
        has_tag_input = True
        tag_values = form.getlist("tags")
        if tag_values:
            raw_parts.extend([v for v in tag_values if isinstance(v, str)])
    if not has_tag_input:
        fallback = data_dict.get("tag_string")
        if isinstance(fallback, str):
            has_tag_input = True
            raw_parts.append(fallback)
    tokens = []
    for part in raw_parts:
        tokens.extend([t.strip() for t in part.replace(",", " ").split() if t.strip()])
    seen = set()
    tags_payload = []
    for tag in tokens:
        lower_tag = tag.lower()
        if lower_tag in seen:
            continue
        seen.add(lower_tag)
        tags_payload.append({"name": tag})
    return has_tag_input, tags_payload


def hydrate_tag_string(dataset_dict, fallback_tag_string=None):
    """Ensure template-facing tag_string is present from tags payload."""
    if not isinstance(dataset_dict, dict):
        return dataset_dict
    if isinstance(fallback_tag_string, str):
        dataset_dict["tag_string"] = fallback_tag_string
        return dataset_dict
    tags = dataset_dict.get("tags") or []
    tag_names = []
    for item in tags:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = getattr(item, "name", None)
        if isinstance(name, str) and name.strip():
            tag_names.append(name.strip())
    dataset_dict["tag_string"] = " ".join(tag_names)
    return dataset_dict


# ...existing code from previous fdf_tags.py...
