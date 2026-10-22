import importlib

import pytest
from ckan.plugins import toolkit
from ckan.tests import factories

# The module, not the Blueprint of the same name blueprints/__init__.py
# re-exports.
download_all = importlib.import_module("ckanext.fair3r.blueprints.download_all")


@pytest.mark.ckan_config("ckan.plugins", "fair3r")
@pytest.mark.usefixtures("clean_db", "with_plugins")
class TestDownloadAll:
    def _get(self, app, dataset):
        return app.get(
            toolkit.url_for("download_all.download", id=dataset["name"]),
            follow_redirects=False,
        )

    def test_only_zenodo_files_redirects_to_zenodos_own_zip(self, app, monkeypatch):
        dataset = factories.Dataset()
        factories.Resource(package_id=dataset["id"], url="https://zenodo.org/records/1")
        zip_url = "https://zenodo.org/api/records/1/files-archive"
        monkeypatch.setattr(
            download_all, "fair3r_zenodo_files_archive_url", lambda _id: zip_url
        )

        response = self._get(app, dataset)

        assert response.status_code in (301, 302, 303)
        assert response.headers["Location"] == zip_url

    def test_nothing_to_download_is_still_a_404(self, app, monkeypatch):
        dataset = factories.Dataset()
        factories.Resource(package_id=dataset["id"], url="https://example.org/x")
        monkeypatch.setattr(
            download_all, "fair3r_zenodo_files_archive_url", lambda _id: None
        )

        assert self._get(app, dataset).status_code == 404


def test_files_with_the_same_name_keep_distinct_names_in_the_zip():
    used = {"dataset-metadata.txt"}

    names = [download_all._unique_arcname(n, used) for n in ("a.csv", "a.csv", "a.csv")]

    assert names == ["a.csv", "a-2.csv", "a-3.csv"]
