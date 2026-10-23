"""
Custom CKAN actions for ckanext-fair3r.

These are registered via IActions in plugin.py and exposed automatically
at /api/3/action/<name> — no blueprint or Nginx changes required.
"""


def fdf_completeness(context, data_dict):
    """Completeness of a dataset being edited, from the live form values."""
    import json

    from ckanext.fair3r.lib.fdf.completeness import compute_completeness
    from ckanext.fair3r.lib.fdf.schema import load_fdf_schema

    try:
        fdf_data = json.loads(data_dict.get("fdf_output_json") or "{}")
    except (TypeError, ValueError):
        fdf_data = {}
    if not isinstance(fdf_data, dict):
        fdf_data = {}

    tag_string = data_dict.get("tag_string") or ""
    pkg = {
        "title": data_dict.get("title"),
        "notes": data_dict.get("notes"),
        "tags": [t for t in tag_string.split(",") if t.strip()],
        "license_id": data_dict.get("license_id"),
    }
    result = compute_completeness(load_fdf_schema(), fdf_data, pkg)
    result["missing"] = [list(m) for m in result["missing"]]
    return result


def fdf_completeness_auth(context, data_dict):
    """Any logged-in editor may ask for the completeness of the form they edit."""
    return {"success": bool(context.get("user") or context.get("auth_user_obj"))}
