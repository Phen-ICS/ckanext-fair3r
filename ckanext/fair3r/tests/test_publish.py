import pytest
from ckan import model
from ckan.plugins import toolkit
from ckan.tests import factories


def _post(app, dataset, token):
    return app.post(
        toolkit.url_for("publish.publish_dataset", id=dataset["name"]),
        headers={"Authorization": token},
        follow_redirects=False,
    )


@pytest.mark.ckan_config("ckan.plugins", "fair3r")
@pytest.mark.usefixtures("clean_db", "with_plugins")
class TestPublish:
    def test_publish_makes_the_dataset_public(self, app):
        user = factories.SysadminWithToken()
        dataset = factories.Dataset(
            owner_org=factories.Organization()["id"], private=True
        )

        response = _post(app, dataset, user["token"])

        assert response.status_code in (302, 303)
        model.Session.expire_all()
        assert model.Package.get(dataset["id"]).private is False

    def test_publish_requires_edit_rights(self, app):
        stranger = factories.UserWithToken()
        dataset = factories.Dataset(
            owner_org=factories.Organization()["id"], private=True
        )

        response = _post(app, dataset, stranger["token"])

        assert response.status_code in (403, 404)
        model.Session.expire_all()
        assert model.Package.get(dataset["id"]).private is True

    def test_failed_publish_keeps_the_dataset_private(self, app, monkeypatch):
        # e.g. ckanext-doi refusing incomplete metadata
        user = factories.SysadminWithToken()
        dataset = factories.Dataset(
            owner_org=factories.Organization()["id"], private=True
        )
        real_get_action = toolkit.get_action

        def get_action(name):
            if name != "package_patch":
                return real_get_action(name)

            def fail(context, data_dict):
                raise ValueError("Creator name must be supplied")

            return fail

        monkeypatch.setattr(toolkit, "get_action", get_action)

        response = _post(app, dataset, user["token"])

        assert response.status_code in (302, 303)
        model.Session.expire_all()
        assert model.Package.get(dataset["id"]).private is True


@pytest.mark.ckan_config("ckan.plugins", "fair3r")
@pytest.mark.usefixtures("clean_db", "with_plugins")
class TestPublishButton:
    def _page(self, app, dataset, token):
        return app.get(
            toolkit.url_for("dataset.read", id=dataset["name"]),
            headers={"Authorization": token},
        ).body

    def test_private_dataset_shows_the_publish_button(self, app):
        user = factories.SysadminWithToken()
        dataset = factories.Dataset(
            owner_org=factories.Organization()["id"], private=True
        )

        body = self._page(app, dataset, user["token"])

        assert f"/dataset/{dataset['name']}/publish" in body

    def test_public_dataset_shows_the_published_badge_instead(self, app):
        user = factories.SysadminWithToken()
        dataset = factories.Dataset(
            owner_org=factories.Organization()["id"], private=False
        )

        body = self._page(app, dataset, user["token"])

        assert f"/dataset/{dataset['name']}/publish" not in body
        assert "Published" in body
