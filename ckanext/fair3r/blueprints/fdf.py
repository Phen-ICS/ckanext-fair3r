"""
FDF (Fair3R Dataset Form) Blueprint

This blueprint handles the FDF dataset creation form, which is part of ckanext-fair3r.
"""

import logging

from ckan import logic, model
from ckan.common import _
from ckan.plugins import toolkit
from flask import Blueprint, redirect, request

from ckanext.fair3r.lib.decorators import login_required
from ckanext.fair3r.lib.fdf.context import build_fdf_context
from ckanext.fair3r.lib.fdf.doi import sync_datacite_metadata
from ckanext.fair3r.lib.fdf.form import extract_fdf_output_json
from ckanext.fair3r.lib.fdf.package import prepare_fdf_package_data
from ckanext.fair3r.lib.fdf.render import (
    dispatch_standard_dataset_edit,
    render_fdf_create_template,
    render_fdf_dataset_edit,
)
from ckanext.fair3r.lib.fdf.schema import load_fdf_schema
from ckanext.fair3r.lib.fdf.utils import is_fdf_dataset
from ckanext.fair3r.lib.fdf.validation import validate_fdf_output_json

log = logging.getLogger(__name__)


fdf = Blueprint("fdf", __name__)

NotAuthorized = logic.NotAuthorized
NotFound = logic.NotFound
ValidationError = logic.ValidationError
get_action = logic.get_action


@fdf.route("/dataset/new/fdf", methods=["GET", "POST"])
@login_required(redirect_to="user.login")
def fdf_dataset_creation():
    """
    Render standard CKAN new dataset page with FDF metadata fields appended.
    Handles both GET (display form) and POST (submit form).
    """
    package_type = "dataset"
    context = build_fdf_context()
    schema_json = load_fdf_schema()

    # Handle POST - form submission
    if request.method == "POST":
        try:
            # Get form data

            # IMPORTANT: Extract fdf_output_json BEFORE clean_dict might remove it
            fdf_output_json = request.form.get("fdf_output_json")

            fdf_output_json, fdf_errors, fdf_error_summary = extract_fdf_output_json(
                request.form, schema_json, validate_fdf_output_json
            )
            if fdf_errors:
                errors = fdf_errors
                error_summary = fdf_error_summary
                raise ValidationError(errors)

            data_dict = prepare_fdf_package_data(
                request.form,
                package_type,
                fdf_output_json,
                state="draft",
                log_label="create",
            )

            # Create the dataset
            created_package = get_action("package_create")(context, data_dict)

            try:
                sync_datacite_metadata(
                    created_package, context, toolkit, logic.get_action
                )
            except Exception:
                log.exception("Fallback DOI sync failed after package_create")

            # Redirect to add resources
            return redirect(
                toolkit.url_for("dataset_resource.new", id=created_package.get("name"))
            )

        except ValidationError as e:
            model.Session.rollback()
            log.error("Validation error: %s", e.error_dict)
            errors = e.error_dict or {
                _("FAIR Metadata (FDF)"): [_("Validation failed")]
            }
            error_summary = e.error_summary or {
                k: v[0] if isinstance(v, list) and v else str(v)
                for k, v in errors.items()
            }
        except NotAuthorized:
            model.Session.rollback()
            log.error("Not authorized to create dataset")
            toolkit.abort(403, toolkit._("Unauthorized to create a package"))
        except Exception as e:
            model.Session.rollback()
            log.exception("Error creating dataset")
            errors = {"error": [str(e)]}
            error_summary = {_("Error"): str(e)}
    else:
        # GET - display form
        errors = {}
        error_summary = {}

    # Get form data from POST or use empty dict
    data = request.form.to_dict() if request.method == "POST" else {}
    return render_fdf_create_template(
        data, errors, error_summary, package_type, schema_json, context
    )


@fdf.route("/dataset/edit/<id>", methods=["GET", "POST"])
@login_required(redirect_to="user.login")
def fdf_dataset_edit_dispatch(id):
    """
    Canonical dataset edit entrypoint.

    Uses FDF edit flow only for datasets containing a valid `fdf_output_json`.
    Falls back to the standard CKAN edit flow otherwise.
    """
    context = build_fdf_context(for_edit=True)

    try:
        pkg_dict = logic.get_action("package_show")(context, {"id": id})
    except (logic.NotFound, logic.NotAuthorized):
        return dispatch_standard_dataset_edit(id=id, package_type="dataset")
    except Exception:  # noqa: BLE001
        return dispatch_standard_dataset_edit(id=id, package_type="dataset")

    if is_fdf_dataset(pkg_dict):
        return render_fdf_dataset_edit(id=id, initial_pkg_dict=pkg_dict)

    return dispatch_standard_dataset_edit(id=id, package_type="dataset")
