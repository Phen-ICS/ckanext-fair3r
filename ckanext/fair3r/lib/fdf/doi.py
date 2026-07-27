"""
FDF DataCite/DOI sync utilities.
"""

import logging

from ckan.common import _

from ckanext.doi.lib.api import DataciteClient  # type: ignore
from ckanext.doi.lib.metadata import build_metadata_dict, build_xml_dict  # type: ignore
from ckanext.doi.model.crud import DOIQuery  # type: ignore

log = logging.getLogger(__name__)


def sync_datacite_metadata(pkg_dict, context, toolkit, get_action):
    """
    Fallback DOI sync when IPackageController hooks are not triggered.
    Mirrors ckanext-doi logic from DOIPlugin.after_dataset_update.
    """
    if pkg_dict.get("state", "active") != "active" or pkg_dict.get("private", False):
        return
    package_id = pkg_dict.get("id")
    if not package_id:
        return
    doi_context = dict(context or {})
    doi_context.pop("schema", None)
    pkg_show_dict = get_action("package_show")(doi_context, {"id": package_id})
    doi = DOIQuery.read_package(package_id, create_if_none=True)
    metadata_dict = build_metadata_dict(pkg_show_dict)
    xml_dict = build_xml_dict(metadata_dict)

    def _build_minimal_xml_dict(source_metadata_dict):
        creators = []
        for creator in source_metadata_dict.get("creators", []) or []:
            if not isinstance(creator, dict):
                continue
            full_name = creator.get("full_name")
            if isinstance(full_name, str):
                full_name = full_name.strip()
            if not full_name:
                continue
            creator_entry = {
                "name": full_name,
                "nameType": "Organizational" if creator.get("is_org") else "Personal",
            }
            creators.append(creator_entry)
        titles = []
        for title in source_metadata_dict.get("titles", []) or []:
            if not isinstance(title, dict):
                continue
            title_text = title.get("title")
            if isinstance(title_text, str):
                title_text = title_text.strip()
            if title_text:
                titles.append({"title": title_text})
        publisher = source_metadata_dict.get("publisher")
        if isinstance(publisher, str):
            publisher = publisher.strip()
        publication_year = source_metadata_dict.get("publicationYear")
        resource_type = source_metadata_dict.get("resourceType") or "Dataset"
        minimal = {
            "creators": creators,
            "titles": titles,
            "publisher": publisher,
            "publicationYear": str(publication_year) if publication_year else None,
            "types": {
                "resourceType": resource_type,
                "resourceTypeGeneral": "Dataset",
            },
            "schemaVersion": "http://datacite.org/schema/kernel-4",
        }
        descriptions = []
        for description in source_metadata_dict.get("descriptions", []) or []:
            if not isinstance(description, dict):
                continue
            description_text = description.get("description")
            if isinstance(description_text, str):
                description_text = description_text.strip()
            if description_text:
                descriptions.append(
                    {
                        "descriptionType": description.get("descriptionType")
                        or "Abstract",
                        "description": description_text,
                    }
                )
        if descriptions:
            minimal["descriptions"] = descriptions[:1]
        return minimal

    def _set_metadata_with_fallback(
        doi_identifier, full_xml_dict, source_metadata_dict
    ):
        minimal_xml_dict = _build_minimal_xml_dict(source_metadata_dict)
        minimal_without_desc = dict(minimal_xml_dict)
        minimal_without_desc.pop("descriptions", None)
        attempts = [
            ("full", full_xml_dict),
            ("minimal", minimal_xml_dict),
            ("minimal_no_descriptions", minimal_without_desc),
        ]
        last_error = None
        client = DataciteClient()
        for index, (attempt_name, payload) in enumerate(attempts):
            try:
                client.set_metadata(doi_identifier, payload)
                if index == 0:
                    return False
                log.info(
                    'DOI sync: Metadata accepted with fallback payload "%s" for DOI %s',
                    attempt_name,
                    doi_identifier,
                )
                return True
            except Exception as err:
                last_error = err
                if "minLength" not in str(err):
                    raise
                log.warning(
                    'DOI sync: DataCite minLength validation failed for payload "%s". DOI=%s Error=%s',
                    attempt_name,
                    doi_identifier,
                    err,
                )
        if last_error:
            raise last_error
        return True

    client = DataciteClient()
    if doi.published is None:
        try:
            used_fallback = _set_metadata_with_fallback(
                doi.identifier, xml_dict, metadata_dict
            )
            client.mint_doi(doi.identifier, package_id)
            try:
                if used_fallback:
                    toolkit.h.flash_success(
                        _("DataCite DOI created (metadata fallback applied)")
                    )
                else:
                    toolkit.h.flash_success(_("DataCite DOI created"))
            except Exception:  # noqa: BLE001
                log.debug("Unable to display DOI creation flash message")
        except Exception as e:
            if "minLength" in str(e):
                log.error(f"DataCite DOI creation failed: {e}")
                try:
                    toolkit.h.flash_error(
                        _(
                            "DataCite metadata validation warning (minLength). Dataset saved; DOI metadata update skipped for now."
                        )
                    )
                except Exception:  # noqa: BLE001
                    log.debug("Unable to display DOI validation flash error")
                return
            log.error(f"DataCite DOI creation failed: {e}")
            raise
    else:
        try:
            same = client.check_for_update(doi.identifier, xml_dict)
            if not same:
                used_fallback = _set_metadata_with_fallback(
                    doi.identifier, xml_dict, metadata_dict
                )
                try:
                    if used_fallback:
                        toolkit.h.flash_success(
                            _("DataCite DOI metadata updated (fallback applied)")
                        )
                    else:
                        toolkit.h.flash_success(_("DataCite DOI metadata updated"))
                except Exception:  # noqa: BLE001
                    log.debug("Unable to display DOI update flash message")
        except Exception as e:
            if "minLength" in str(e):
                log.error(f"DataCite DOI update failed: {e}")
                try:
                    toolkit.h.flash_error(
                        _(
                            "DataCite metadata update warning (minLength). Dataset was updated locally."
                        )
                    )
                except Exception:  # noqa: BLE001
                    log.debug("Unable to display DOI update flash error")
                return
            log.error(f"DataCite DOI update failed: {e}")
            raise
