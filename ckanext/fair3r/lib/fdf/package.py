"""
FDF package data preparation utilities.
"""

from ckanext.fair3r.lib.fdf.extras import sync_fdf_contact_fields, sync_fdf_extras
from ckanext.fair3r.lib.fdf.form import clean_form_data
from ckanext.fair3r.lib.fdf.tags import build_tags_payload_from_request


def prepare_fdf_package_data(
    form, package_type, fdf_output_json, package_id=None, state=None, log_label="create"
):
    data_dict = clean_form_data(form)
    data_dict["type"] = package_type
    if package_id:
        data_dict["id"] = package_id
    if state is not None:
        data_dict["state"] = state
    has_tag_input, tags_payload = build_tags_payload_from_request(form, data_dict)
    if has_tag_input:
        data_dict["tags"] = tags_payload
    sync_fdf_extras(data_dict, fdf_output_json, log_label)
    sync_fdf_contact_fields(data_dict, fdf_output_json, log_label)
    return data_dict
