"""
FDF context utilities.
"""

import ckan.model as model
import ckan.plugins.toolkit as toolkit


def build_fdf_context(for_edit=False):
    context = {
        "model": model,
        "session": model.Session,
        "user": toolkit.current_user.name,
        "auth_user_obj": toolkit.current_user,
    }
    if for_edit:
        context["for_edit"] = True
    return context
