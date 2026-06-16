"""Tests for the ckanext.fair3r plugin module."""

import os
import json
import types
import ckanext.fair3r.plugin as plugin


class DummyUser:
    def __init__(self, is_anonymous=False, sysadmin=False):
        self.is_anonymous = is_anonymous
        self.sysadmin = sysadmin


def test_plugin_class_and_instantiation():
    assert hasattr(plugin, "Fair3RPlugin")
    p = plugin.Fair3RPlugin()
    assert p is not None
    assert isinstance(p, plugin.Fair3RPlugin)


def test_get_helpers_keys():
    p = plugin.Fair3RPlugin()
    helpers = p.get_helpers()
    expected = [
        "fair3r_current_user",
        "fair3r_is_authenticated",
        "fair3r_is_resource_read",
        "fair3r_context",
        "fair3r_is_superadmin",
        "fdf_schema",
        "parse_fdf_json",
        "fdf_schema_sections",
        "extract_fdf_section_data",
        "fair3r_license_options",
    ]
    for key in expected:
        assert key in helpers


def test_parse_fdf_json_valid_and_invalid():
    p = plugin.Fair3RPlugin()
    valid = '{"foo": 1}'
    invalid = "{foo: 1}"
    assert p.parse_fdf_json(valid) == {"foo": 1}
    assert p.parse_fdf_json("") == {}
    assert p.parse_fdf_json(None) == {}
    assert p.parse_fdf_json(invalid) == {}


def test_fair3r_is_superadmin_and_authenticated(monkeypatch):
    p = plugin.Fair3RPlugin()
    monkeypatch.setattr(
        plugin, "current_user", DummyUser(is_anonymous=False, sysadmin=True)
    )
    assert p.fair3r_is_superadmin() is True
    assert p.fair3r_is_authenticated() is True
    monkeypatch.setattr(
        plugin, "current_user", DummyUser(is_anonymous=True, sysadmin=False)
    )
    assert p.fair3r_is_superadmin() is False
    assert p.fair3r_is_authenticated() is False


def test_fair3r_current_user(monkeypatch):
    p = plugin.Fair3RPlugin()
    dummy = DummyUser()
    monkeypatch.setattr(plugin, "current_user", dummy)
    assert p.fair3r_current_user() is dummy


def test_fair3r_license_options():
    p = plugin.Fair3RPlugin()

    class DummyH:
        @staticmethod
        def license_options(existing_license_id=None):
            return [
                ("cc-zero", "Creative Commons Zero"),
                ("odc-by", "Open Data Commons Attribution"),
            ]

    import sys

    sys.modules["ckan.lib.helpers"] = types.SimpleNamespace(
        license_options=DummyH.license_options
    )
    opts = p.fair3r_license_options()
    assert any("CC0" in desc for _, desc in opts)
    assert any("ODC-By" in desc for _, desc in opts)


def test_get_fdf_schema_sections(tmp_path, monkeypatch):
    p = plugin.Fair3RPlugin()
    schema = {
        "sections": [
            {
                "id": "s1",
                "title": "Section 1",
                "icon": "i1",
                "display_mapping": {"source": "foo"},
            },
            {
                "id": "s2",
                "title": "Section 2",
                "icon": "i2",
                "display_mapping": {"source": "bar"},
            },
        ]
    }
    schema_path = tmp_path / "fdf_schema.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f)
    monkeypatch.setattr(os.path, "dirname", lambda _: str(tmp_path))
    monkeypatch.setattr(plugin, "__file__", str(tmp_path / "plugin.py"))
    orig_open = open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("fdf_schema.json"):
            return orig_open(schema_path, *args, **kwargs)
        return orig_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)
    sections = p._get_fdf_schema_sections()
    assert len(sections) == 2
    assert sections[0]["id"] == "s1"


def test_extract_fdf_section_data_simple():
    p = plugin.Fair3RPlugin()
    fdf_data = {
        "subjects": [
            {"subjectScheme": "NCBITaxon", "val": 1},
            {"subjectScheme": "Other", "val": 2},
        ]
    }
    section = {
        "display_mapping": {
            "source": "subjects",
            "filter": {"subjectScheme": "NCBITaxon"},
        }
    }
    result = p.extract_fdf_section_data(fdf_data, section)
    assert isinstance(result, list)
    assert all(subj["subjectScheme"] == "NCBITaxon" for subj in result)


def test_extract_fdf_section_data_direct():
    p = plugin.Fair3RPlugin()
    fdf_data = {"foo": 123}
    section = {"display_mapping": {"source": "foo"}}
    assert p.extract_fdf_section_data(fdf_data, section) == 123


def test_extract_fdf_section_data_related_identifiers_ignores_empty_entries():
    p = plugin.Fair3RPlugin()
    fdf_data = {
        "relatedIdentifiers": [
            {
                "relatedIdentifierType": "URL",
                "relationType": "References",
            },
            {
                "relatedIdentifier": "https://example.org/protocol",
                "relatedIdentifierType": "URL",
                "relationType": "References",
            },
        ]
    }
    section = {"display_mapping": {"source": "relatedIdentifiers"}}

    result = p.extract_fdf_section_data(fdf_data, section)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["relatedIdentifier"] == "https://example.org/protocol"


def test_extract_fdf_section_data_contributors_ignores_empty_entries():
    p = plugin.Fair3RPlugin()
    fdf_data = {
        "contributors": [
            {"name": "   ", "contributorType": ""},
            {
                "name": "Jane Doe",
                "contributorType": "DataManager",
                "nameType": "Personal",
            },
        ]
    }
    section = {
        "display_mapping": {
            "source": "contributors",
        }
    }

    result = p.extract_fdf_section_data(fdf_data, section)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["name"] == "Jane Doe"


def test_extract_fdf_section_data_contributors_ignores_type_only_entries():
    p = plugin.Fair3RPlugin()
    fdf_data = {
        "contributors": [
            {
                "contributorType": "DataManager",
                "nameType": "Personal",
            },
            {
                "name": "Valid Contributor",
                "contributorType": "DataManager",
                "nameType": "Personal",
            },
        ]
    }
    section = {
        "display_mapping": {
            "source": "contributors",
        }
    }

    result = p.extract_fdf_section_data(fdf_data, section)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["name"] == "Valid Contributor"


def test_extract_fdf_section_data_contributors_independent_of_creators():
    """Contributors and Creators are now independent: a person may appear in
    both lists without being filtered out."""
    p = plugin.Fair3RPlugin()
    fdf_data = {
        "creators": [
            {
                "nameType": "Personal",
                "givenName": "Jane",
                "familyName": "Doe",
            }
        ],
        "contributors": [
            {
                "nameType": "Personal",
                "givenName": "Jane",
                "familyName": "Doe",
                "contributorType": "Researcher",
            },
            {
                "name": "Research Lab A",
                "nameType": "Organizational",
                "contributorType": "HostingInstitution",
            },
        ],
    }
    section = {
        "display_mapping": {
            "source": "contributors",
        }
    }

    result = p.extract_fdf_section_data(fdf_data, section)

    assert isinstance(result, list)
    assert len(result) == 2
    names = {entry["name"] for entry in result if entry.get("name")}
    assert "Research Lab A" in names


def test_extract_fdf_section_data_repeatable_composite_keeps_treatment_fields_without_subjects():
    p = plugin.Fair3RPlugin()
    fdf_data = {
        "subjects": [],
        "treatmentProtocol": ["acute"],
        "treatmentDesign": ["50 mg/kg IP daily for 7 days"],
    }
    section = {
        "display_mapping": {
            "source": ["subjects", "treatmentProtocol", "treatmentDesign"],
            "filter": {"subjectScheme": "ChEBI"},
        }
    }

    result = p.extract_fdf_section_data(fdf_data, section)

    assert isinstance(result, dict)
    assert result["treatmentProtocol"] == ["acute"]
    assert result["treatmentDesign"] == ["50 mg/kg IP daily for 7 days"]
    assert "subjects" not in result


def test_build_metadata_dict_parses_scalar_datacite_extras():
    p = plugin.Fair3RPlugin()
    pkg_dict = {
        "extras": [
            {
                "key": "datacite.publisherIdentifier",
                "value": "https://ror.org/03cjqqq10",
            },
            {"key": "datacite.publisherIdentifierScheme", "value": "ROR"},
            {"key": "datacite.schemeURI", "value": "https://ror.org/"},
        ]
    }
    metadata_dict = {}
    errors = {
        "publisherIdentifier": "missing",
        "publisherIdentifierScheme": "missing",
        "schemeURI": "missing",
    }

    out_metadata, out_errors = p.build_metadata_dict(pkg_dict, metadata_dict, errors)

    assert out_metadata["publisherIdentifier"] == "https://ror.org/03cjqqq10"
    assert out_metadata["publisherIdentifierScheme"] == "ROR"
    assert out_metadata["schemeURI"] == "https://ror.org/"
    assert "publisherIdentifier" not in out_errors
    assert "publisherIdentifierScheme" not in out_errors
    assert "schemeURI" not in out_errors


def test_build_metadata_dict_prefers_datacite_creators_with_identifiers():
    p = plugin.Fair3RPlugin()
    pkg_dict = {
        "extras": [
            {
                "key": "datacite.creators",
                "value": json.dumps(
                    [
                        {
                            "full_name": "Bouri, Laurent",
                            "given_name": "Laurent",
                            "family_name": "Bouri",
                            "is_org": False,
                            "identifiers": [
                                {
                                    "identifier": "https://orcid.org/0000-0001-2345-6789",
                                    "scheme": "ORCID",
                                    "scheme_uri": "https://orcid.org/",
                                }
                            ],
                            "affiliations": ["Institut Clinique de la Souris"],
                        }
                    ]
                ),
            }
        ]
    }
    metadata_dict = {
        "creators": [
            {
                "full_name": "Bouri, Laurent",
                "given_name": "Laurent",
                "family_name": "Bouri",
                "is_org": False,
            }
        ]
    }
    errors = {"creators": "missing"}

    out_metadata, out_errors = p.build_metadata_dict(pkg_dict, metadata_dict, errors)

    assert out_metadata.get("creators")
    creator = out_metadata["creators"][0]
    assert creator["full_name"] == "Bouri, Laurent"
    assert creator.get("identifiers")
    assert creator["identifiers"][0]["scheme"] == "ORCID"
    assert creator.get("affiliations") == ["Institut Clinique de la Souris"]
    assert "creators" not in out_errors


def test_build_metadata_dict_prefers_specific_contributor_over_researcher():
    p = plugin.Fair3RPlugin()
    pkg_dict = {
        "extras": [
            {
                "key": "datacite.contributors",
                "value": json.dumps(
                    [
                        {
                            "name": "Bosc, Nathanael",
                            "givenName": "Nathanael",
                            "familyName": "Bosc",
                            "nameType": "Personal",
                            "contributorType": "ContactPerson",
                            "nameIdentifiers": [
                                {
                                    "nameIdentifier": "https://orcid.org/0000-0001-2345-6789",
                                    "nameIdentifierScheme": "ORCID",
                                    "schemeURI": "https://orcid.org/",
                                }
                            ],
                        }
                    ]
                ),
            }
        ]
    }
    metadata_dict = {
        "contributors": [
            {
                "full_name": "Bosc, Nathanael",
                "given_name": "Nathanael",
                "family_name": "Bosc",
                "is_org": False,
                "contributor_type": "Researcher",
            }
        ]
    }
    errors = {"contributors": "missing"}

    out_metadata, out_errors = p.build_metadata_dict(pkg_dict, metadata_dict, errors)

    assert out_metadata.get("contributors")
    contributors = out_metadata["contributors"]
    assert len(contributors) == 1
    contributor = contributors[0]
    assert contributor["full_name"] == "Bosc, Nathanael"
    assert contributor.get("contributor_type") == "ContactPerson"
    assert contributor.get("identifiers")
    assert contributor["identifiers"][0]["scheme"] == "ORCID"
    assert "contributors" not in out_errors
