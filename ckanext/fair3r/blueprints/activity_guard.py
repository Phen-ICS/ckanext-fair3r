from ckan import authz, logic, model
from ckan.common import current_user
from ckan.plugins import toolkit
from flask import Blueprint, request

activity_guard = Blueprint("fair3r_activity_guard", __name__)


def _members_only(next_auth, context, data_dict):
    group = model.Group.get(data_dict.get("id"))
    if group and not authz.has_user_permission_for_group_or_org(
        group.id, context.get("user"), "read"
    ):
        return {
            "success": False,
            "msg": toolkit._("Only members can see this activity stream"),
        }
    return next_auth(context, data_dict)


# Members-only activity streams, for the API as well as the pages (which
# call these same actions). No auth_allow_anonymous_access: anonymous
# callers are refused before these even run.
@toolkit.chained_auth_function
def organization_activity_list(next_auth, context, data_dict):
    return _members_only(next_auth, context, data_dict)


@toolkit.chained_auth_function
def group_activity_list(next_auth, context, data_dict):
    return _members_only(next_auth, context, data_dict)


@activity_guard.before_app_request
def restrict_activity_streams():
    """Show a small forbidden page, instead of CKAN's bare 403, when a
    non-member opens an organization/group activity stream (the rule itself
    is the auth functions above)."""
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

    group_type = (
        "organization" if endpoint.endswith("organization_activity") else "group"
    )

    # Get group/org dict to obtain canonical id for membership check and
    # to pass into the template when rendering the forbidden page.
    context = {"ignore_auth": True, "for_view": True}
    try:
        group_dict = toolkit.get_action(f"{group_type}_show")(  # type: ignore
            context, {"id": obj_id_or_name}
        )
    except (toolkit.ObjectNotFound, logic.NotFound):
        # Let the original view handle 404 / errors
        return None
    except Exception:  # noqa: BLE001
        # Let the original view handle 404 / errors
        return None

    try:
        toolkit.check_access(
            f"{group_type}_activity_list",
            {"user": current_user.name},
            {"id": group_dict["id"]},
        )
    except toolkit.NotAuthorized:
        template = f"{group_type}/activity_forbidden.html"
        extra_vars = {
            "id": obj_id_or_name,
            "group_dict": group_dict,
            "group_type": group_dict.get("type", group_type),
        }
        return toolkit.render(template, extra_vars=extra_vars)

    return None
