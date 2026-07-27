"""
FDF form options utilities.
Provides helper(s) to fetch available groups, organizations, and licenses for FDF forms.
"""

from ckan import model
from ckan.logic import NotAuthorized
from ckan.plugins.toolkit import get_action


def get_fdf_form_options(context):
    """Fetch common select options needed by FDF create/draft forms."""
    model.Session.rollback()
    try:
        groups_available = get_action("group_list")(
            context, {"all_fields": True, "type": "group"}
        )
    except NotAuthorized:
        groups_available = []

    try:
        orgs_available = get_action("organization_list")(context, {"all_fields": True})
    except NotAuthorized:
        orgs_available = []

    licences = [
        {"id": license_item.get("id"), "title": license_item.get("title")}
        for license_item in get_action("license_list")(context, {})
    ]

    return groups_available, orgs_available, licences
