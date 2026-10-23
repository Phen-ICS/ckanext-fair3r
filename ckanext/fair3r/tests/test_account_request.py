import importlib

import pytest
from ckan.plugins import toolkit

# The module, not the Blueprint of the same name blueprints/__init__.py
# re-exports.
account_request = importlib.import_module("ckanext.fair3r.blueprints.account_request")


class _FakeRedis:
    def __init__(self):
        self.counts = {}

    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key, seconds):
        pass


@pytest.mark.ckan_config("ckan.plugins", "fair3r")
@pytest.mark.ckan_config("ckanext.contact.mail_to", "admin@example.org")
@pytest.mark.usefixtures("with_plugins")
def test_account_requests_stop_at_the_hourly_limit(app, monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(account_request, "connect_to_redis", lambda: redis)
    monkeypatch.setattr(account_request, "ACCOUNT_REQUESTS_PER_HOUR", 2)
    sent = []
    monkeypatch.setattr(
        account_request.ckan_mailer,
        "mail_recipient",
        lambda **kwargs: sent.append(kwargs["recipient_email"]),
    )
    form = {"email": "a@example.org", "name": "A", "message": "please"}
    url = toolkit.url_for("account_request.request_account")

    for _ in range(3):
        app.post(url, data=form)

    assert sent == ["admin@example.org", "admin@example.org"]
