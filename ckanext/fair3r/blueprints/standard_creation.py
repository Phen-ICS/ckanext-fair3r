"""
Standard CKAN Dataset Creation Blueprint

This blueprint exposes a direct route to the standard CKAN dataset creation form,
bypassing any custom choice or FDF logic. Useful when the extension overrides /dataset/new.
"""

from flask import Blueprint, request

try:
    from ckan.views.dataset import CreateView
except ImportError:
    # Fallback for some CKAN installations
    from ckanext.dataset.views import CreateView

standard_creation = Blueprint("standard_creation", __name__)


@standard_creation.route("/dataset/new/standard", methods=["GET", "POST"])
def standard_dataset_creation():
    """
    Direct access to standard CKAN dataset creation.
    This route provides direct access to the standard CKAN dataset creation
    interface, bypassing the choice page.
    """
    if request.method == "POST":
        return CreateView().post(package_type="dataset")
    return CreateView().get(package_type="dataset")
