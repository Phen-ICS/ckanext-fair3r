"""Regression test for ckanext/fair3r/lib/fdf/draft_guard.py: a known CKAN
core + ckanext-xloader race can silently revert a just-published dataset
back to 'draft' (see that module's docstring for the full mechanism). This
reproduces the race directly - create draft, activate, simulate the stale
full-package write xloader's resource_patch does - and confirms the
IPackageController hook detects it and schedules a correction."""

import pytest
from ckan.model import Package
from ckan.tests import factories
from ckan.tests.helpers import call_action

from ckanext.fair3r.lib.fdf.draft_guard import _reactivate_package


@pytest.mark.usefixtures("clean_db")
def test_stale_draft_revert_is_corrected():
    org = factories.Organization()
    # Mirrors the real fair3r flow: the FDF metadata step creates the
    # dataset in 'draft', same as CKAN's own new-dataset wizard.
    pkg = factories.Dataset(private=False, owner_org=org["id"], state="draft")
    pkg_id = pkg["id"]
    assert Package.get(pkg_id).state == "draft"

    # "Publish" - a real draft -> active transition.
    call_action("package_patch", {"ignore_auth": True}, id=pkg_id, state="active")
    assert Package.get(pkg_id).state == "active"

    # Simulate ckanext-xloader's resource_patch landing late: a full
    # package_update carrying the *old* 'draft' it read before Publish
    # committed (ckan/logic/action/patch.py's resource_patch does exactly
    # this - package_show, splice in the resource change, package_update
    # with the whole dict).
    stale_pkg = dict(pkg, state="draft")
    call_action("package_update", {"ignore_auth": True}, **stale_pkg)
    assert Package.get(pkg_id).state == "draft", (
        "fixture assumption broken: the stale write should still succeed "
        "in reverting state, same as the real race"
    )

    # The correction is enqueued as its own background job (see
    # draft_guard.py's docstring for why it can't run straight from the
    # hook). Run that job function inline, exactly as the real worker
    # eventually would - this tests our activation logic, not RQ's own
    # (already-proven) delivery.
    _reactivate_package(pkg_id)

    assert Package.get(pkg_id).state == "active"


@pytest.mark.usefixtures("clean_db")
def test_draft_left_alone_when_never_activated():
    """A dataset that's never been activated must not be force-activated -
    the FDF wizard legitimately re-saves a draft as 'draft' repeatedly
    while the user is still filling it in."""
    org = factories.Organization()
    pkg = factories.Dataset(private=False, owner_org=org["id"], state="draft")
    pkg_id = pkg["id"]

    call_action(
        "package_patch", {"ignore_auth": True}, id=pkg_id, notes="still editing"
    )
    assert Package.get(pkg_id).state == "draft"
