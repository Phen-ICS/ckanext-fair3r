from flask import Blueprint, request

import ckan.plugins.toolkit as toolkit


activity_guard_bp = Blueprint("fair3r_activity_guard", __name__)


@activity_guard_bp.before_app_request
def restrict_activity_streams():
    """Restrict access to organization/group activity streams to members only.

    This runs before all requests. If the endpoint is one of the activity
    stream views, and the current user is not a member of the target
    organization/group, render a small forbidden page instead of the stream.
    """
    endpoint = request.endpoint or ""
    if endpoint not in (
        "activity.organization_activity",
        "activity.group_activity",
    ):
        return None

    view_args = request.view_args or {}
    obj_id_or_name = view_args.get("id")
    if not obj_id_or_name:
        return None

    group_type = "organization" if endpoint.endswith("organization_activity") else "group"

    # Get group/org dict to obtain canonical id for membership check and
    # to pass into the template when rendering the forbidden page.
    context = {"ignore_auth": True, "for_view": True}
    try:
        group_dict = toolkit.get_action(f"{group_type}_show")(  # type: ignore
            context, {"id": obj_id_or_name}
        )
    except Exception:
        # Let the original view handle 404 / errors
        return None

    # Membership check using core helper
    from ckan.lib import helpers as h  # imported here to avoid cyclic imports

    if not h.user_in_org_or_group(group_dict["id"]):
        template = f"{group_type}/activity_forbidden.html"
        extra_vars = {
            "id": obj_id_or_name,
            "group_dict": group_dict,
            "group_type": group_dict.get("type", group_type),
        }
        return toolkit.render(template, extra_vars=extra_vars)

    return None


