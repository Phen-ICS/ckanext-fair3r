"""
FDF form data utilities.
"""

import ckan.logic as logic
from ckan.lib.navl import dictization_functions as dict_fns


def clean_form_data(form):
    return logic.clean_dict(
        dict_fns.unflatten(logic.tuplize_dict(logic.parse_params(form)))
    )


def extract_fdf_output_json(form, schema_json, validate_fdf_output_json):
    fdf_output_json = form.get("fdf_output_json")
    _, fdf_errors, fdf_error_summary = validate_fdf_output_json(
        fdf_output_json, schema_json
    )
    return fdf_output_json, fdf_errors, fdf_error_summary
