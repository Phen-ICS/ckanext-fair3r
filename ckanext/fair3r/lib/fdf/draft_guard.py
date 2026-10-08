"""Self-heals a known CKAN core + ckanext-xloader race that can silently
revert a dataset from 'active' back to 'draft' after it was correctly
published.

The root cause (found by reading ckan/logic/action/patch.py and
update.py): resource_patch/resource_update don't do a targeted SQL update -
they fetch the *whole* package via package_show, splice in the one changed
resource, and write the whole thing back via package_update. xloader calls
resource_patch from its own background job once a resource's data finishes
loading into the DataStore. If that job's read happens before the "Publish"
button's package_patch(state='active') commits, but its own write commits
after, it overwrites 'active' with the stale 'draft' it read - the dataset
silently stops being published, with no error anywhere.

A bounded wait-then-activate approach (see
ckanext-fair3r/public/base/js/resource-upload.js) can only narrow this
race, never close it - there's no delay long enough to guarantee the
racing job has finished. This takes the opposite approach: don't guess how
long to wait, react to the race whenever it actually happens. A dataset
seen 'active' is remembered (a few minutes, in Redis) as "should stay
active"; if it's then written back to 'draft' within that window - not
something a legitimate editor does via a resource-level action - that's
recognised as this race and corrected via package_revise (a locked read,
so this correction can't itself be undone the same way).

The correction itself is enqueued as a background job rather than called
straight from this hook: after_dataset_update fires from inside the
*caller's own* database transaction (CKAN wraps package saves in a nested
SQLAlchemy transaction and only runs IPackageController hooks once a real
change is detected, before that transaction commits), and package_revise
manages its own top-level transaction - calling it synchronously here
raises ResourceClosedError (confirmed directly: SQLAlchemy won't let one
action's commit nest inside another's still-open transaction). Running it
as its own RQ job sidesteps that entirely, in a fresh transaction, and
still needs no page-level wait: the same worker process that runs
xloader's jobs picks this one up straight away.
"""

import logging

from ckan.lib.redis import connect_to_redis
from ckan.plugins import toolkit

log = logging.getLogger(__name__)

RECENTLY_ACTIVATED_TTL_SECONDS = 120
REDIS_KEY_PREFIX = "fair3r:recently_activated:"


def _redis():
    try:
        return connect_to_redis()
    except Exception:
        log.exception("draft_guard: could not connect to Redis")
        return None


def guard_against_stale_draft_revert(pkg_dict):
    """Call from IPackageController.after_dataset_update. Cheap no-op for
    every normal update; only acts on the specific state transitions that
    matter."""
    if pkg_dict.get("type", "dataset") != "dataset":
        return

    package_id = pkg_dict.get("id")
    state = pkg_dict.get("state")
    if not package_id or state not in ("active", "draft"):
        return

    redis = _redis()
    if redis is None:
        return

    key = REDIS_KEY_PREFIX + package_id

    if state == "active":
        # Remembers "this dataset should stay active" for a while - cheap,
        # self-expiring, no migration needed. Refreshed on every active
        # write, including our own correction below.
        redis.set(key, "1", ex=RECENTLY_ACTIVATED_TTL_SECONDS)
        return

    # state == 'draft' here. Only act if we saw it active recently -
    # otherwise this is a perfectly normal draft (still being created, or
    # legitimately never activated) and must be left alone.
    if not redis.get(key):
        return

    log.warning(
        "Dataset %s reverted to draft within %ss of being activated - "
        "reactivating it (known CKAN core/xloader resource_patch race, "
        "see ckanext/fair3r/lib/fdf/draft_guard.py)",
        package_id,
        RECENTLY_ACTIVATED_TTL_SECONDS,
    )
    toolkit.enqueue_job(
        _reactivate_package,
        kwargs={"package_id": package_id},
        title=f"fair3r draft_guard: reactivate {package_id}",
    )


def _reactivate_package(package_id):
    """Runs as its own RQ job - see the module docstring for why this can't
    just be called straight from the hook above."""
    try:
        toolkit.get_action("package_revise")(
            {"ignore_auth": True},
            {"match": {"id": package_id}, "update": {"state": "active"}},
        )
    except Exception:
        log.exception(
            "draft_guard: failed to reactivate dataset %s after stale draft revert",
            package_id,
        )
