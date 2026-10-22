import pytest
from ckan.plugins import toolkit
from ckan.tests import factories


@pytest.mark.ckan_config("ckan.plugins", "fair3r activity")
class TestMembersOnlyActivity:
    @pytest.fixture(autouse=True)
    def _activity_tables(self, clean_db, with_plugins, migrate_db_for):
        migrate_db_for("activity")

    def _api(self, app, org, headers=None):
        return app.get(
            "/api/3/action/organization_activity_list",
            query_string={"id": org["name"]},
            headers=headers or {},
        )

    def test_api_refuses_anonymous_and_non_members(self, app):
        org = factories.Organization()
        stranger = factories.UserWithToken()

        assert self._api(app, org).status_code == 403
        assert (
            self._api(app, org, {"Authorization": stranger["token"]}).status_code == 403
        )

    def test_api_allows_members(self, app):
        member = factories.UserWithToken()
        org = factories.Organization(
            users=[{"name": member["name"], "capacity": "member"}]
        )

        response = self._api(app, org, {"Authorization": member["token"]})

        assert response.status_code == 200

    def test_page_still_shows_the_members_only_notice(self, app):
        org = factories.Organization()
        stranger = factories.UserWithToken()

        response = app.get(
            toolkit.url_for("activity.organization_activity", id=org["name"]),
            headers={"Authorization": stranger["token"]},
        )

        assert response.status_code == 200
        assert "You do not have permission to view this activity stream" in (
            response.body
        )
