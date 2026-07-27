"""
FDF template rendering utilities.
"""

import logging

from ckan import logic
from ckan.common import _
from ckan.plugins import toolkit
from flask import current_app, redirect, request

from ckanext.fair3r.lib.fdf.context import build_fdf_context as _build_fdf_context
from ckanext.fair3r.lib.fdf.doi import sync_datacite_metadata as _sync_datacite_metadata
from ckanext.fair3r.lib.fdf.form import (
    extract_fdf_output_json as _extract_fdf_output_json,
)
from ckanext.fair3r.lib.fdf.options import get_fdf_form_options
from ckanext.fair3r.lib.fdf.package import (
    prepare_fdf_package_data as _prepare_fdf_package_data,
)
from ckanext.fair3r.lib.fdf.schema import load_fdf_schema as _load_fdf_schema
from ckanext.fair3r.lib.fdf.tags import hydrate_tag_string as _hydrate_tag_string
from ckanext.fair3r.lib.fdf.validation import validate_fdf_output_json

log = logging.getLogger(__name__)


def render_fdf_dataset_edit(id, initial_pkg_dict=None):
    """
    Edit an existing dataset using FDF form.
    Handles both GET (display form with FDF data) and POST (submit updated FDF data).
    """
    context = _build_fdf_context(for_edit=True)

    # Load the existing dataset
    if initial_pkg_dict is not None:
        pkg_dict = initial_pkg_dict
        _hydrate_tag_string(pkg_dict)
    else:
        try:
            pkg_dict = logic.get_action("package_show")(context, {"id": id})
            _hydrate_tag_string(pkg_dict)
        except (logic.NotFound, logic.NotAuthorized):
            log.error("Dataset not found or not authorized: %s", id)
            raise

    package_type = "dataset"
    is_draft = (pkg_dict.get("state") or "").startswith("draft")
    errors = {}
    error_summary = {}

    schema_json = _load_fdf_schema()

    # Handle POST - form submission
    if request.method == "POST":
        try:
            log.info("★ POST request to canonical edit flow for dataset=%s", id)
            log.info("★ request.form.keys(): %s", list(request.form.keys()))

            # Extract fdf_output_json from the edited form
            fdf_output_json = request.form.get("fdf_output_json")
            log.info(
                "★ fdf_output_json extracted from form: %s",
                "YES" if fdf_output_json else "NO",
            )

            fdf_output_json, fdf_errors, fdf_error_summary = _extract_fdf_output_json(
                request.form, schema_json, validate_fdf_output_json
            )
            if fdf_errors:
                errors = fdf_errors
                error_summary = fdf_error_summary
                raise logic.ValidationError(errors)

            if fdf_output_json:
                log.info("★ fdf_output_json length: %d", len(fdf_output_json))

            # Build data_dict from form data
            data_dict = _prepare_fdf_package_data(
                request.form,
                package_type,
                fdf_output_json,
                package_id=id,
                state="draft" if is_draft else None,
                log_label="update",
            )
            if is_draft:
                context["allow_state_change"] = True

            # Use package_patch for partial updates to avoid dropping existing resources
            # when the edit form does not submit the resources array.
            pkg_dict = logic.get_action("package_patch")(context, data_dict)

            try:
                _sync_datacite_metadata(pkg_dict, context, toolkit, logic.get_action)
            except Exception:
                log.exception("Fallback DOI sync failed after package_patch")

            log.info("★ Dataset updated successfully: %s", pkg_dict.get("id"))

            if is_draft:
                return redirect(
                    toolkit.url_for("dataset_resource.new", id=pkg_dict["name"])
                )

            # Redirect to dataset page
            return redirect(toolkit.url_for("dataset.read", id=pkg_dict["id"]))

        except logic.ValidationError as e:
            log.error("Validation error updating dataset: %s", e.error_dict)
            errors = e.error_dict or {
                _("FAIR Metadata (FDF)"): [_("Validation failed")]
            }
            error_summary = {
                k: v[0] if isinstance(v, list) and v else str(v)
                for k, v in errors.items()
            }
            _hydrate_tag_string(pkg_dict, request.form.get("tag_string"))
        except Exception as e:
            log.exception("Unexpected error updating dataset")
            toolkit.h.flash_error(_("Error: %(message)s") % {"message": str(e)[:100]})
            return redirect(toolkit.url_for("dataset.read", id=id))

    _hydrate_tag_string(pkg_dict)

    if is_draft:
        draft_data = dict(pkg_dict)
        if request.method == "POST":
            draft_data.update(request.form.to_dict())
        _hydrate_tag_string(draft_data, request.form.get("tag_string"))
        return render_fdf_create_template(
            draft_data, errors, error_summary, package_type, schema_json, context
        )

    return render_fdf_edit_template(
        pkg_dict, errors, error_summary, package_type, schema_json
    )


def render_fdf_create_template(
    data, errors, error_summary, package_type, schema_json, context, stage=None
):
    groups_available, orgs_available, licences = get_fdf_form_options(context)
    return toolkit.render(
        "package/new_fdf.html",
        {
            "data": data,
            "errors": errors,
            "error_summary": error_summary,
            "dataset_type": package_type,
            "stage": stage or ["active"],
            "licences": licences,
            "groups_available": groups_available,
            "orgs_available": orgs_available,
            "fdf_schema": schema_json,
            "use_fdf": True,
        },
    )


def render_fdf_edit_template(
    pkg_dict, errors, error_summary, package_type, schema_json
):
    return toolkit.render(
        "package/edit_fdf.html",
        {
            "pkg_dict": pkg_dict,
            "errors": errors,
            "error_summary": error_summary,
            "dataset_type": package_type,
            "fdf_schema": schema_json,
            "use_fdf": True,
        },
    )


def dispatch_standard_dataset_edit(id, package_type="dataset"):
    """Delegate to CKAN standard dataset edit view when FDF mode is not applicable."""
    standard_edit_view = current_app.view_functions.get("dataset.edit")
    if standard_edit_view:
        return standard_edit_view(id=id, package_type=package_type)
    return redirect(toolkit.url_for("dataset.read", id=id))
