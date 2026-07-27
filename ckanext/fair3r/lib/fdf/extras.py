"""
FDF extras and contact fields utilities.
"""

import logging

from ckanext.fair3r.lib.fdf.converter import fdf_json_to_ckan_dataset
from ckanext.fair3r.lib.fdf.datacite_converter import convert_fdf_to_datacite_extras

log = logging.getLogger(__name__)


def upsert_extra(extras_list, key, value):
    for extra in extras_list:
        if isinstance(extra, dict) and extra.get("key") == key:
            extra["value"] = value
            return
    extras_list.append({"key": key, "value": value})


def sync_fdf_extras(data_dict, fdf_output_json, log_label):
    if not (isinstance(fdf_output_json, str) and fdf_output_json.strip()):
        return
    if "extras" not in data_dict:
        data_dict["extras"] = []
    upsert_extra(data_dict["extras"], "fdf_output_json", fdf_output_json)
    try:
        datacite_extras = convert_fdf_to_datacite_extras(fdf_output_json)
        if datacite_extras:
            data_dict["extras"] = [
                e
                for e in data_dict["extras"]
                if not (
                    isinstance(e, dict)
                    and isinstance(e.get("key"), str)
                    and e.get("key", "").startswith("datacite.")
                )
            ]
            data_dict["extras"].extend(datacite_extras)
            log.info(
                "★ Added %d datacite.* extras in %s flow",
                len(datacite_extras),
                log_label,
            )
    except Exception:
        log.exception(
            "Error generating datacite.* extras in %s flow",
            log_label,
        )


def sync_fdf_contact_fields(data_dict, fdf_output_json, log_label):
    if not (isinstance(fdf_output_json, str) and fdf_output_json.strip()):
        return
    try:
        log.info("★ Extracting author/maintainer from FDF data in %s", log_label)
        fdf_fields = fdf_json_to_ckan_dataset(fdf_output_json)
        if fdf_fields.get("author"):
            data_dict["author"] = fdf_fields["author"]
            log.info("★ SET author=%s", fdf_fields["author"])
        if fdf_fields.get("author_email"):
            data_dict["author_email"] = fdf_fields["author_email"]
            log.info("★ SET author_email=%s", fdf_fields["author_email"])
        if fdf_fields.get("maintainer"):
            data_dict["maintainer"] = fdf_fields["maintainer"]
            log.info("★ SET maintainer=%s", fdf_fields["maintainer"])
        if fdf_fields.get("maintainer_email"):
            data_dict["maintainer_email"] = fdf_fields["maintainer_email"]
            log.info("★ SET maintainer_email=%s", fdf_fields["maintainer_email"])
    except Exception:
        log.exception(
            "Error extracting author/maintainer from FDF data in %s",
            log_label,
        )
