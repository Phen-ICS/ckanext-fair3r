"""ckanext-zenodo is genuinely installed in this dev environment (same
container, same /plugins mount) - exercising the real import here is a
useful sanity check that this module's assumption about
routing_config_dict()'s shape still holds, on top of being the realistic
case. The ImportError fallback path (zenodo not installed) isn't
independently unit-tested for the same reason noted in
ckanext-zenodo's own test_publish_guard.py: there's no way to make it
genuinely unimportable here without breaking every other test that
relies on it being present."""

import json

from ckanext.fair3r.lib.zenodo_routing import fair3r_zenodo_routing_config


def test_returns_valid_json_with_expected_keys():
    raw = fair3r_zenodo_routing_config()

    assert raw is not None
    config = json.loads(raw)
    assert set(config.keys()) == {"max_resource_size_bytes", "xloader_formats"}
    assert isinstance(config["max_resource_size_bytes"], int)
    assert isinstance(config["xloader_formats"], list)
