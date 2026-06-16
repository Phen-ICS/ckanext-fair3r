"""
Dataset Creation Blueprint

This blueprint handles the neutral dataset creation choice page that allows users
to choose between different dataset creation methods (CKAN standard & FDF).
"""

import logging

from flask import Blueprint, redirect
import ckan.plugins.toolkit as toolkit
from ckanext.fair3r.lib.decorators import login_required
from ckanext.fair3r.lib.utils import asbool

log = logging.getLogger(__name__)

dataset_choice = Blueprint("dataset_choice", __name__)


@dataset_choice.route("/dataset/new")
@login_required(redirect_to="account_request.request_account")
def dataset_creation():
    """
    Show dataset creation choice page.

    This route shows a choice between:
    - Standard CKAN form
    - FDF (Fair3R Dataset Form) interface
    """
    # Evaluate configuration flags
    enable_fdf = asbool(
        toolkit.config.get("ckanext.fair3r.enable_fdf_integration", True)
    )

    # If FDF is disabled, just fall back to the normal CKAN flow
    if not enable_fdf:
        return redirect(toolkit.url_for("standard_creation.standard_dataset_creation"))
    else:
        return toolkit.render(
            "package/creation_choice.html",
            {
                "pkg_dict": None,
                "dataset_type": "dataset",
                "enable_fdf": enable_fdf,
            },
        )
