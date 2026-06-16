"""
FDF dataset and form utilities.
"""


def is_fdf_dataset(pkg_dict):
    """Return True when the package has a fdf_output_json extra (marks it as FDF-created)."""
    extras = pkg_dict.get("extras", []) or []
    return any(
        (e.get("key") if isinstance(e, dict) else getattr(e, "key", None))
        == "fdf_output_json"
        for e in extras
    )
