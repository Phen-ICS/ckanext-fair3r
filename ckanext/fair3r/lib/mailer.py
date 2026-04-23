# encoding: utf-8
from __future__ import annotations

import logging
from typing import Any, Optional

import ckan.model as model
from ckan.common import config
from ckan.lib.base import render
import ckan.lib.mailer as ckan_mailer

log = logging.getLogger(__name__)


def get_reset_link_body(user: model.User) -> str:
    """
    Get the body of the password reset email in HTML format.
    This function overrides the default CKAN function.
    """
    extra_vars = {
        "reset_link": ckan_mailer.get_reset_link(user),
        "site_title": config.get("ckan.site_title"),
        "site_url": config.get("ckan.site_url"),
        "user_name": user.name,
    }
    # NOTE: This template is translated
    return render("emails/html/reset_password.html", extra_vars)


def get_invite_body(
    user: model.User,
    group_dict: Optional[dict[str, Any]] = None,
    role: Optional[str] = None,
) -> str:
    """
    Get the body of the invitation email in HTML format.
    This function overrides the default CKAN function.
    """
    from ckan.lib.helpers import roles_translated

    extra_vars = {
        "reset_link": ckan_mailer.get_reset_link(user),
        "site_title": config.get("ckan.site_title"),
        "site_url": config.get("ckan.site_url"),
        "user_name": user.name,
    }

    if role:
        extra_vars["role_name"] = roles_translated().get(role, role)
    if group_dict:
        from ckan.common import _

        group_type = _("organization") if group_dict["is_organization"] else _("group")
        extra_vars["group_type"] = group_type
        extra_vars["group_title"] = group_dict.get("title")

    # NOTE: This template is translated
    return render("emails/html/invite_user.html", extra_vars)


def send_reset_link(user: model.User) -> None:
    """
    Send a password reset email to the user.
    This function overrides the default CKAN function.
    """
    ckan_mailer.create_reset_key(user)
    body_html = get_reset_link_body(user)

    extra_vars = {"site_title": config.get("ckan.site_title")}
    subject = render("emails/reset_password_subject.txt", extra_vars)

    # Make sure we only use the first line
    subject = subject.split("\n")[0]

    ckan_mailer.mail_user(user, subject, body_html, body_html=body_html)


def send_invite(
    user: model.User,
    group_dict: Optional[dict[str, Any]] = None,
    role: Optional[str] = None,
) -> None:
    """
    Send an invitation email to the user.
    This function overrides the default CKAN function.
    """
    ckan_mailer.create_reset_key(user)
    body_html = get_invite_body(user, group_dict, role)

    extra_vars = {"site_title": config.get("ckan.site_title")}
    subject = render("emails/invite_user_subject.txt", extra_vars)

    # Make sure we only use the first line
    subject = subject.split("\n")[0]

    ckan_mailer.mail_user(user, subject, body_html, body_html=body_html)
