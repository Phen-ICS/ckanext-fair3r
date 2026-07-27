import copy
import json

from ckanext.fair3r.lib.fdf.validation import (
    _validate_duplicate_people,
    _validate_required_fields,
    _validate_vocabularies,
    validate_fdf_output_json,
)

MINIMAL_SCHEMA = {
    "vocabularies": {
        "organism_presets": {
            "items": [
                {
                    "id": "http://purl.obolibrary.org/obo/NCBITaxon_10090",
                    "label": "Mus musculus",
                    "triggers": ["strain_search", "gene_search"],
                },
                {
                    "id": "http://purl.obolibrary.org/obo/NCBITaxon_10116",
                    "label": "Rattus norvegicus",
                    "triggers": ["strain_search", "gene_search"],
                },
                {
                    "id": "http://purl.obolibrary.org/obo/NCBITaxon_7955",
                    "label": "Danio rerio",
                    "triggers": ["gene_search"],
                },
            ]
        }
    },
    "sections": [
        {
            "id": "organism",
            "title": "Biological Model",
            "fields": [
                {
                    "id": "organism_choice",
                    "label": "Model Organism",
                    "required": True,
                    "output": {
                        "path": "subjects",
                        "mode": "append",
                        "tpl": {
                            "subject": "$label",
                            "subjectScheme": "NCBITaxon",
                            "valueURI": "$id",
                        },
                    },
                }
            ],
        },
        {
            "id": "strain",
            "title": "Genetic Background / Strain",
            "condition": {"type": "organism_trigger", "trigger": "strain_search"},
            "subject_scheme": "Strain",
            "fields": [
                {
                    "id": "strain_search",
                    "label": "Strain or Line",
                    "required": True,
                    "output": {
                        "path": "subjects",
                        "mode": "append",
                        "tpl": {
                            "subject": "Strain: $label",
                            "subjectScheme": "Strain",
                            "valueURI": "$id",
                        },
                    },
                }
            ],
        },
    ],
}


def _organism_subject(taxon_uri, label):
    return {
        "subject": label,
        "subjectScheme": "NCBITaxon",
        "valueURI": taxon_uri,
    }


def test_strain_required_for_mouse_when_missing():
    fdf_data = {
        "subjects": [
            _organism_subject(
                "http://purl.obolibrary.org/obo/NCBITaxon_10090", "Mus musculus"
            )
        ]
    }

    errors = _validate_required_fields(copy.deepcopy(MINIMAL_SCHEMA), fdf_data)

    assert "Genetic Background / Strain" in errors
    assert "Strain or Line: required field." in errors["Genetic Background / Strain"]


def test_strain_required_for_rat_when_missing():
    fdf_data = {
        "subjects": [
            _organism_subject(
                "http://purl.obolibrary.org/obo/NCBITaxon_10116",
                "Rattus norvegicus",
            )
        ]
    }

    errors = _validate_required_fields(copy.deepcopy(MINIMAL_SCHEMA), fdf_data)

    assert "Genetic Background / Strain" in errors
    assert "Strain or Line: required field." in errors["Genetic Background / Strain"]


def test_strain_not_required_for_zebrafish_when_missing():
    fdf_data = {
        "subjects": [
            _organism_subject(
                "http://purl.obolibrary.org/obo/NCBITaxon_7955", "Danio rerio"
            )
        ]
    }

    errors = _validate_required_fields(copy.deepcopy(MINIMAL_SCHEMA), fdf_data)

    assert "Genetic Background / Strain" not in errors


def test_strain_required_for_mouse_is_satisfied_when_present():
    fdf_data = {
        "subjects": [
            _organism_subject(
                "http://purl.obolibrary.org/obo/NCBITaxon_10090", "Mus musculus"
            ),
            {
                "subject": "Strain: C57BL/6J",
                "subjectScheme": "Strain",
                "valueURI": "http://example.org/strain/c57bl6j",
            },
        ]
    }

    errors = _validate_required_fields(copy.deepcopy(MINIMAL_SCHEMA), fdf_data)

    assert "Genetic Background / Strain" not in errors


def test_validate_fdf_output_json_rejects_invalid_json():
    _, errors, error_summary = validate_fdf_output_json("{invalid-json", MINIMAL_SCHEMA)

    assert "FAIR Metadata (FDF)" in errors
    assert errors["FAIR Metadata (FDF)"] == ["FDF payload is not valid JSON."]
    assert error_summary["FAIR Metadata (FDF)"] == "FDF payload is not valid JSON."


def test_duplicate_creators_are_rejected():
    """Two creator entries with the same identity are always rejected,
    regardless of any contributors."""
    fdf_data = {
        "creators": [
            {
                "givenName": "Alice",
                "familyName": "Doe",
                "email": "alice@example.org",
            },
            {
                "givenName": "Alice",
                "familyName": "Doe",
                "email": "alice@example.org",
            },
        ],
        "contributors": [],
    }

    errors = _validate_duplicate_people(fdf_data)

    assert "Authors & Contributors" in errors
    assert (
        "Duplicate author/maintainer entry at item #2."
        in errors["Authors & Contributors"]
    )


def test_validate_vocabularies_flags_unknown_credit_role_uri():
    schema = {
        "vocabularies": {
            "credit_roles": {
                "items": [
                    {
                        "id": "https://credit.niso.org/contributor-roles/conceptualization/",
                        "label": "Conceptualization",
                    }
                ]
            }
        },
        "sections": [
            {
                "id": "creators",
                "title": "Creators",
                "fields": [
                    {
                        "id": "contributor_roles",
                        "label": "Project Contributions (CRediT)",
                        "type": "multi_select",
                        "vocabulary": "credit_roles",
                        "output": {"path": "contributors", "mode": "append_from_array"},
                    }
                ],
            }
        ],
    }
    fdf_data = {
        "contributors": [
            {
                "name": "Alice Doe",
                "contributorRoles": [
                    {
                        "contributorRole": "Unknown role",
                        "contributorRoleURI": "https://example.org/credit/unknown",
                    }
                ],
            }
        ]
    }

    errors = _validate_vocabularies(schema, fdf_data)

    assert "Creators" in errors
    assert (
        "Project Contributions (CRediT): value 'https://example.org/credit/unknown' "
        "is outside allowed vocabulary."
    ) in errors["Creators"]


def test_validate_fdf_output_json_populates_summary_for_duplicate_people():
    fdf_data = {
        "creators": [
            {
                "givenName": "Alice",
                "familyName": "Doe",
                "email": "alice@example.org",
            },
            {
                "givenName": "Alice",
                "familyName": "Doe",
                "email": "alice@example.org",
            },
        ],
        "contributors": [
            {"name": "Alice Doe", "contributorType": "Researcher"},
        ],
    }

    _, errors, error_summary = validate_fdf_output_json(
        json.dumps(fdf_data), {"sections": [], "vocabularies": {}, "apis": {}}
    )

    assert "Authors & Contributors" in errors
    assert "Authors & Contributors" in error_summary
    assert (
        error_summary["Authors & Contributors"] == errors["Authors & Contributors"][0]
    )
