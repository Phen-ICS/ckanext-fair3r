import json
import sys
import uuid

import pytest
from ckan.plugins import toolkit
from ckan.tests import factories, helpers


@pytest.mark.ckan_config("ckan.plugins", "fair3r")
@pytest.mark.usefixtures("clean_db", "with_plugins")
class TestBlueprintRoutes:
    def test_dataset_choice_route_requires_auth(self, app):
        url = toolkit.url_for("dataset_choice.dataset_creation")
        response = app.get(url, follow_redirects=False)

        assert response.status_code in (302, 303)
        assert "/account/request" in response.headers.get("Location", "")

    def test_fdf_route_requires_auth(self, app):
        url = toolkit.url_for("fdf.fdf_dataset_creation")
        response = app.get(url, follow_redirects=False)

        assert response.status_code in (302, 303)
        assert "/user/login" in response.headers.get("Location", "")

    def test_fdf_route_with_token_is_accessible(self, app):
        user = factories.UserWithToken()
        url = toolkit.url_for("fdf.fdf_dataset_creation")
        response = app.get(
            url,
            headers={"Authorization": user["token"]},
            follow_redirects=False,
        )

        assert response.status_code == 200

    def test_fdf_create_with_token_creates_dataset(self, app):
        user = factories.SysadminWithToken()
        dataset_name = f"fdf-token-{uuid.uuid4().hex[:8]}"
        url = toolkit.url_for("fdf.fdf_dataset_creation")
        fdf_payload = json.dumps(
            {
                "publicationYear": 2024,
                "types": [
                    {"resourceType": "Dataset", "resourceTypeGeneral": "Dataset"}
                ],
                "publisher": "Institut Clinique de la souris",
                "publisherIdentifier": "https://ror.org/03cjqqq10",
                "creators": [
                    {
                        "givenName": "Alice",
                        "familyName": "Example",
                        "nameType": "Personal",
                        "email": "alice@example.org",
                    }
                ],
                "subjects": [
                    {
                        "subject": "Mus musculus",
                        "subjectScheme": "NCBITaxon",
                        "valueURI": "http://purl.obolibrary.org/obo/NCBITaxon_10090",
                        "schemeURI": "http://purl.obolibrary.org/obo/",
                    },
                    {
                        "subject": "Strain: C57BL/6J",
                        "subjectScheme": "speciesBackground",
                        "valueURI": "http://www.informatics.jax.org/strain/MGI:3028467",
                    },
                ],
                "contributors": [
                    {
                        "contributorType": "DataManager",
                        "nameType": "Personal",
                        "givenName": "Bob",
                        "familyName": "Manager",
                    }
                ],
            }
        )

        response = app.post(
            url,
            headers={"Authorization": user["token"]},
            data={
                "name": dataset_name,
                "title": "Dataset created with token",
                "notes": "Created by authenticated blueprint test",
                "fdf_output_json": fdf_payload,
            },
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)
        assert f"/dataset/{dataset_name}/resource/new" in response.headers.get(
            "Location", ""
        )

        package = helpers.call_action("package_show", id=dataset_name)
        assert package["name"] == dataset_name
        assert package["author"] == "Alice Example"

    def test_fdf_edit_dispatch_routes_to_fdf_view_for_fdf_dataset(self, monkeypatch):
        fdf_module = sys.modules["ckanext.fair3r.blueprints.fdf"]
        pkg_dict = {"id": "dataset-id", "name": "dataset-name", "extras": []}

        monkeypatch.setattr(
            fdf_module,
            "build_fdf_context",
            lambda for_edit=True: {"user": "tester", "for_edit": for_edit},
        )
        real_get_action_fdf = fdf_module.logic.get_action

        def _patched_get_action_fdf(action_name):
            if action_name == "package_show":
                return lambda context, data_dict: pkg_dict
            return real_get_action_fdf(action_name)

        monkeypatch.setattr(fdf_module.logic, "get_action", _patched_get_action_fdf)
        monkeypatch.setattr(fdf_module, "is_fdf_dataset", lambda _pkg: True)
        monkeypatch.setattr(
            fdf_module,
            "render_fdf_dataset_edit",
            lambda id, initial_pkg_dict=None: {
                "route": "fdf",
                "id": id,
                "pkg": initial_pkg_dict,
            },
        )
        monkeypatch.setattr(
            fdf_module,
            "dispatch_standard_dataset_edit",
            lambda **kwargs: {"route": "standard", "kwargs": kwargs},
        )

        result = fdf_module.fdf_dataset_edit_dispatch.__wrapped__("dataset-id")

        assert result["route"] == "fdf"
        assert result["id"] == "dataset-id"
        assert result["pkg"] == pkg_dict

    def test_fdf_edit_dispatch_routes_to_standard_for_non_fdf_dataset(
        self, monkeypatch
    ):
        fdf_module = sys.modules["ckanext.fair3r.blueprints.fdf"]
        monkeypatch.setattr(
            fdf_module,
            "build_fdf_context",
            lambda for_edit=True: {"user": "tester", "for_edit": for_edit},
        )
        real_get_action_nonfdf = fdf_module.logic.get_action

        def _patched_get_action_nonfdf(action_name):
            if action_name == "package_show":
                return lambda context, data_dict: {
                    "id": "dataset-id",
                    "name": "dataset-name",
                }
            return real_get_action_nonfdf(action_name)

        monkeypatch.setattr(fdf_module.logic, "get_action", _patched_get_action_nonfdf)
        monkeypatch.setattr(fdf_module, "is_fdf_dataset", lambda _pkg: False)
        monkeypatch.setattr(
            fdf_module,
            "dispatch_standard_dataset_edit",
            lambda **kwargs: {"route": "standard", "kwargs": kwargs},
        )

        result = fdf_module.fdf_dataset_edit_dispatch.__wrapped__("dataset-id")

        assert result["route"] == "standard"
        assert result["kwargs"] == {"id": "dataset-id", "package_type": "dataset"}

    def test_fdf_edit_dispatch_falls_back_to_standard_when_package_show_fails(
        self, monkeypatch
    ):
        fdf_module = sys.modules["ckanext.fair3r.blueprints.fdf"]
        monkeypatch.setattr(
            fdf_module,
            "build_fdf_context",
            lambda for_edit=True: {"user": "tester", "for_edit": for_edit},
        )

        def _raise_error(_context, _data_dict):
            raise RuntimeError("package_show failed")

        real_get_action = fdf_module.logic.get_action

        def _patched_get_action(action_name):
            if action_name == "package_show":
                return _raise_error
            return real_get_action(action_name)

        monkeypatch.setattr(fdf_module.logic, "get_action", _patched_get_action)
        monkeypatch.setattr(
            fdf_module,
            "dispatch_standard_dataset_edit",
            lambda **kwargs: {"route": "standard", "kwargs": kwargs},
        )

        result = fdf_module.fdf_dataset_edit_dispatch.__wrapped__("dataset-id")

        assert result["route"] == "standard"
        assert result["kwargs"] == {"id": "dataset-id", "package_type": "dataset"}
