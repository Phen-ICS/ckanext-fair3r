"""ckanext-zenodo is genuinely installed in the local dev container (same
/plugins mount) but NOT in this extension's own GitLab CI pipeline, which
never installs other fair3r extensions as test dependencies (same as
ckanext-citations' completeness helper, which has no test of its own for
this exact reason). Asserting against the real import made this test
environment-dependent - it passed locally and failed in CI. Fixed by
injecting fake modules into sys.modules instead, so both the "installed"
and "not installed" paths are exercised deterministically regardless of
what's actually on disk."""

import json
import sys
import types

import pytest

from ckanext.fair3r.lib.zenodo_routing import fair3r_zenodo_routing_config

MODULE_PATH = "ckanext.zenodo.lib.zenodo_config"


@pytest.fixture
def fake_zenodo_config_module(monkeypatch):
    """Injects a fake ckanext.zenodo.lib.zenodo_config module so the
    `from ckanext.zenodo.lib.zenodo_config import routing_config_dict`
    import inside fair3r_zenodo_routing_config() succeeds, whatever
    routing_config_dict() is set to on the returned fake module - without
    requiring ckanext-zenodo to be genuinely installed."""
    fake_module = types.ModuleType(MODULE_PATH)
    monkeypatch.setitem(sys.modules, MODULE_PATH, fake_module)
    # the parent packages only need to exist enough for the submodule
    # import to resolve; real ckanext/ckanext.zenodo/ckanext.zenodo.lib
    # packages aren't required for `from <module> import <name>`.
    return fake_module


def test_returns_none_when_zenodo_is_not_installed(monkeypatch):
    # Force the import to fail regardless of whether ckanext-zenodo
    # happens to be genuinely installed in this environment.
    monkeypatch.setitem(sys.modules, MODULE_PATH, None)

    assert fair3r_zenodo_routing_config() is None


def test_returns_json_from_routing_config_dict(fake_zenodo_config_module):
    fake_zenodo_config_module.routing_config_dict = lambda: {
        "max_resource_size_bytes": 20 * 1024 * 1024,
        "xloader_formats": ["csv"],
    }

    raw = fair3r_zenodo_routing_config()

    assert raw is not None
    assert json.loads(raw) == {
        "max_resource_size_bytes": 20 * 1024 * 1024,
        "xloader_formats": ["csv"],
    }


def test_returns_none_when_routing_config_dict_raises(fake_zenodo_config_module):
    def _boom():
        raise RuntimeError("boom")

    fake_zenodo_config_module.routing_config_dict = _boom

    assert fair3r_zenodo_routing_config() is None
