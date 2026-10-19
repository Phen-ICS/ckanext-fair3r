"""One-click "Publish" from the dataset page, instead of Manage ->
Visibility -> Public -> Update.

Publishing is one-way on purpose (DataCite DOI, Zenodo record), so this
is the only direction offered here - making a dataset private again
stays a deliberate Manage -> Visibility edit. The button posts here
through CKAN's own confirm-action module (confirmation dialog + CSRF).
"""

import logging

from ckan import model
from ckan.common import _, current_user
from ckan.lib import base
from ckan.plugins import toolkit
from flask import Blueprint

log = logging.getLogger(__name__)

publish = Blueprint("publish", __name__, url_prefix="/dataset")


@publish.route("/<id>/publish", methods=["POST"])
def publish_dataset(id: str):
    try:
        toolkit.get_action("package_patch")(
            {"user": current_user.name}, {"id": id, "private": False}
        )
    except toolkit.ObjectNotFound:
        return base.abort(404, _("Dataset not found"))
    except toolkit.NotAuthorized:
        return base.abort(403, _("Not authorized to publish this dataset"))
    except Exception as e:
        # e.g. ckanext-doi refusing incomplete metadata ("Creator name must
        # be supplied"): the update never committed, the dataset stays
        # private - say why instead of a 500.
        log.exception("Publishing dataset %s failed", id)
        model.Session.rollback()
        detail = e.error_summary if isinstance(e, toolkit.ValidationError) else str(e)
        toolkit.h.flash_error(
            _("The dataset could not be published and is still private: {}").format(
                detail
            )
        )
    else:
        toolkit.h.flash_success(_("The dataset is now public."))
    return toolkit.redirect_to("dataset.read", id=id)
