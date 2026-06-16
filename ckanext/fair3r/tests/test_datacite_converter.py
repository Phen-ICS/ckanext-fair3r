"""
Tests for DataCite converter

Tests conversion of FDF JSON to DataCite-compatible metadata.
"""

import json
import pytest
import ckanext.fair3r.lib.fdf.datacite_converter as datacite_converter_module
from ckanext.fair3r.lib.fdf.datacite_converter import (
    DataCiteConverter,
    convert_fdf_to_datacite_extras,
    get_datacite_xml,
)


class TestDataCiteConverter:
    """Test FDF to DataCite conversion."""

    def test_basic_conversion(self):
        """Test basic FDF to DataCite conversion."""
        fdf_json = json.dumps(
            {
                "creators": [
                    {
                        "givenName": "John",
                        "familyName": "Smith",
                        "email": "john.smith@example.org",
                        "nameIdentifiers": [
                            {
                                "nameIdentifier": "https://orcid.org/0000-0001-2345-6789",
                                "nameIdentifierScheme": "ORCID",
                                "schemeURI": "https://orcid.org/",
                            }
                        ],
                        "affiliation": [
                            {
                                "affiliation": "Example University",
                                "affiliationIdentifier": "https://ror.org/123456",
                                "affiliationIdentifierScheme": "ROR",
                                "schemeURI": "https://ror.org/",
                            }
                        ],
                    }
                ],
                "publicationYear": 2026,
                "publisher": "Institut Clinique de la souris",
                "publisherIdentifier": "https://ror.org/03cjqqq10",
                "types": [
                    {"resourceType": "Dataset", "resourceTypeGeneral": "Dataset"}
                ],
                "subjects": [
                    {
                        "subject": "Mus musculus",
                        "subjectScheme": "NCBITaxon",
                        "valueURI": "http://purl.obolibrary.org/obo/NCBITaxon_10090",
                        "schemeURI": "http://purl.obolibrary.org/obo/",
                    },
                    {
                        "subject": "Gene: Apoe",
                        "subjectScheme": "GeneID",
                        "valueURI": "https://identifiers.org/ncbigene:11287",
                    },
                ],
                "descriptions": [
                    {
                        "description": "This dataset contains gene expression data...",
                        "descriptionType": "Abstract",
                    }
                ],
            }
        )

        result = DataCiteConverter.fdf_to_datacite(fdf_json)

        # Check creators
        assert "creators" in result
        assert len(result["creators"]) == 1
        assert result["creators"][0]["name"] == "Smith, John"
        assert result["creators"][0]["givenName"] == "John"
        assert result["creators"][0]["familyName"] == "Smith"
        assert result["creators"][0]["nameType"] == "Personal"

        # Check ORCID
        assert "nameIdentifiers" in result["creators"][0]
        assert len(result["creators"][0]["nameIdentifiers"]) == 1
        assert (
            "orcid.org" in result["creators"][0]["nameIdentifiers"][0]["nameIdentifier"]
        )

        # Check affiliation
        assert "affiliation" in result["creators"][0]
        assert (
            result["creators"][0]["affiliation"][0]["affiliation"]
            == "Example University"
        )

        # Check publication year
        assert result["publicationYear"] == "2026"

        # Check publisher mapping
        assert result["publisher"] == "Institut Clinique de la souris"
        assert result["publisherIdentifier"] == "https://ror.org/03cjqqq10"

        # Check resource type
        assert result["types"]["resourceType"] == "Dataset"
        assert result["types"]["resourceTypeGeneral"] == "Dataset"

        # Check subjects
        assert "subjects" in result
        assert len(result["subjects"]) == 3

        ncbi_taxon = next(
            s for s in result["subjects"] if s.get("subjectScheme") == "NCBITaxon"
        )
        assert ncbi_taxon["subject"] == "Mus musculus"

        gene_id = next(
            s for s in result["subjects"] if s.get("subjectScheme") == "GeneID"
        )
        assert gene_id["subject"] == "Apoe"

        gene_symbol = next(
            s for s in result["subjects"] if s.get("subjectScheme") == "geneSymbol"
        )
        assert gene_symbol["subject"] == "Apoe"

        # Check descriptions
        # Converter keeps the provided Abstract description.
        assert "descriptions" in result
        assert len(result["descriptions"]) >= 1
        abstract = next(
            d for d in result["descriptions"] if d["descriptionType"] == "Abstract"
        )
        assert "gene expression" in abstract["description"]

    def test_convert_to_extras(self):
        """Test conversion to CKAN extras format."""
        fdf_json = json.dumps(
            {
                "creators": [
                    {
                        "givenName": "Jane",
                        "familyName": "Doe",
                        "email": "jane@example.org",
                    }
                ],
                "publicationYear": 2026,
                "publisher": "Institut Clinique de la souris",
                "publisherIdentifier": "https://ror.org/03cjqqq10",
                "subjects": [
                    {"subject": "Rattus norvegicus", "subjectScheme": "NCBITaxon"}
                ],
            }
        )

        extras = convert_fdf_to_datacite_extras(fdf_json)

        assert isinstance(extras, list)
        assert len(extras) > 0

        # Check extras format
        for extra in extras:
            assert "key" in extra
            assert "value" in extra
            assert extra["key"].startswith("datacite.")

        # Check specific keys exist
        keys = [e["key"] for e in extras]
        assert "datacite.creators" in keys
        assert "datacite.publicationYear" in keys
        assert "datacite.subjects" in keys
        assert "datacite.publisher" in keys
        assert "datacite.publisherIdentifier" in keys

        # creators payload must be compatible with ckanext-doi xml_utils.create_contributor
        creators_extra = next(e for e in extras if e["key"] == "datacite.creators")
        creators_payload = json.loads(creators_extra["value"])
        assert isinstance(creators_payload, list)
        assert len(creators_payload) == 1
        assert "full_name" in creators_payload[0]
        assert "nameType" not in creators_payload[0]

    def test_datacite_xml_generation(self):
        """Test XML generation for DataCite API."""
        fdf_json = json.dumps(
            {
                "creators": [
                    {
                        "givenName": "Marie",
                        "familyName": "Curie",
                        "email": "marie@example.org",
                    }
                ],
                "publicationYear": 2026,
                "publisher": "Institut Clinique de la souris",
                "publisherIdentifier": "https://ror.org/03cjqqq10",
                "types": [
                    {"resourceType": "Dataset", "resourceTypeGeneral": "Dataset"}
                ],
                "subjects": [{"subject": "Radium", "subjectScheme": "ChEBI"}],
                "descriptions": [
                    {
                        "description": "Radioactivity studies dataset",
                        "descriptionType": "Abstract",
                    }
                ],
            }
        )

        xml = get_datacite_xml(
            fdf_json,
            title="Radium Research Dataset",
            publisher="Example Publisher",
            doi="10.5281/example.12345",
        )

        # Basic XML structure checks
        assert '<?xml version="1.0"' in xml
        assert "<resource" in xml
        assert "</resource>" in xml

        # Check required fields
        assert (
            '<identifier identifierType="DOI">10.5281/example.12345</identifier>' in xml
        )
        assert "<title>Radium Research Dataset</title>" in xml
        assert "<publisher>Institut Clinique de la souris</publisher>" in xml
        assert "<publicationYear>2026</publicationYear>" in xml

        # Check creators
        # The XML builder emits <creatorName ...> and its text content as separate
        # xml_parts entries joined by \n, so we check the parts independently.
        assert "<creators>" in xml
        assert 'nameType="Personal"' in xml
        assert "Curie, Marie" in xml
        assert "<givenName>Marie</givenName>" in xml
        assert "<familyName>Curie</familyName>" in xml

        # Check subjects
        assert "<subjects>" in xml
        assert "Radium" in xml
        assert "ChEBI" in xml

        # Check descriptions
        assert "<descriptions>" in xml
        assert "Radioactivity studies dataset" in xml

    def test_invalid_json(self):
        """Test error handling for invalid JSON."""
        with pytest.raises(ValueError):
            DataCiteConverter.fdf_to_datacite("{invalid json")

    def test_empty_fdf(self):
        """Test conversion with minimal FDF data."""
        fdf_json = json.dumps({})

        result = DataCiteConverter.fdf_to_datacite(fdf_json)

        # Should return dict even if empty
        assert isinstance(result, dict)

    def test_summary_description_dedupes_same_contributor_name(self):
        fdf_json = json.dumps(
            {
                "publicationYear": 2026,
                "types": [
                    {"resourceType": "Dataset", "resourceTypeGeneral": "Dataset"}
                ],
                "creators": [{"givenName": "laurent", "familyName": "bouri"}],
                "contributors": [
                    {"name": "laurent bouri", "contributorType": "Researcher"},
                    {
                        "givenName": "laurent",
                        "familyName": "bouri",
                        "contributorType": "Other",
                        "contributorRoles": [
                            {"contributorRole": "Conceptualization"},
                            {"contributorRole": "Data Curation"},
                        ],
                    },
                    {
                        "givenName": "Fann",
                        "familyName": "Cris",
                        "contributorType": "ContactPerson",
                    },
                ],
            }
        )

        result = DataCiteConverter.fdf_to_datacite(fdf_json)
        methods = next(
            d for d in result["descriptions"] if d["descriptionType"] == "Methods"
        )
        assert (
            "Contributors: bouri, laurent (Conceptualization, Data Curation); Cris, Fann"
            in methods["description"]
        )

    def test_xml_escaping(self):
        """Test that XML special characters are escaped."""
        fdf_json = json.dumps(
            {
                "creators": [
                    {"givenName": "John <script>", "familyName": "O'Brien & Sons"}
                ],
                "publicationYear": 2026,
                "descriptions": [
                    {
                        "description": 'Data with <tags> & special "chars"',
                        "descriptionType": "Abstract",
                    }
                ],
            }
        )

        xml = get_datacite_xml(
            fdf_json,
            title='Title with <tags> & "quotes"',
            publisher="Publisher & Co.",
            doi="10.5281/test.123",
        )

        # Check that special characters are escaped
        assert "&lt;script&gt;" in xml or "script" not in xml  # < should be escaped
        assert "&amp;" in xml  # & should be escaped
        assert "&quot;" in xml or '"' not in xml  # " should be escaped
        assert "&apos;" in xml or "'" not in xml  # ' should be escaped

    def test_summary_includes_gene_locus_and_treatment_details(self):
        """Technical summary should include gene locus and treatment detail fields."""
        fdf_json = json.dumps(
            {
                "creators": [{"givenName": "Alice", "familyName": "Doe"}],
                "publicationYear": 2026,
                "subjects": [
                    {
                        "subject": "Gene: Apoe",
                        "subjectScheme": "GeneID",
                        "valueURI": "https://identifiers.org/ncbigene:11816",
                    },
                    {
                        "subject": "Allele: Apoetm1Unc",
                        "subjectScheme": "AlleleID",
                        "valueURI": "https://identifiers.org/ensembl:ENSMUSG00000002985",
                    },
                    {
                        "subject": "Gene locus: 7:19620966-19630842",
                        "subjectScheme": "GeneLocus",
                        "valueURI": "7:19620966-19630842",
                    },
                    {
                        "subject": "CHEBI:41774",
                        "subjectScheme": "ChEBI",
                        "valueURI": "http://purl.obolibrary.org/obo/CHEBI_41774",
                    },
                ],
                "treatmentProtocol": ["acute"],
                "treatmentDesign": ["50 mg/kg IP daily for 7 days"],
            }
        )

        result = DataCiteConverter.fdf_to_datacite(fdf_json)
        methods = next(
            d
            for d in result.get("descriptions", [])
            if d.get("descriptionType") == "Methods"
        )
        technical_text = methods["description"]

        assert "Alleles:" in technical_text
        assert "Gene chromosome location:" in technical_text
        assert "Treatments:" in technical_text
        assert "protocol=acute" in technical_text
        assert "design=50 mg/kg IP daily for 7 days" in technical_text

    def test_invalid_subject_value_uri_is_dropped(self):
        """Invalid anyURI values (e.g. raw chromosome ranges) must be omitted for DataCite."""
        fdf_json = json.dumps(
            {
                "subjects": [
                    {
                        "subject": "Gene locus: 7:19430034-19433113",
                        "subjectScheme": "GeneLocus",
                        "valueURI": "7:19430034-19433113",
                    },
                    {
                        "subject": "Mus musculus",
                        "subjectScheme": "NCBITaxon",
                        "valueURI": "http://purl.obolibrary.org/obo/NCBITaxon_10090",
                    },
                ]
            }
        )

        result = DataCiteConverter.fdf_to_datacite(fdf_json)
        assert "subjects" in result
        assert len(result["subjects"]) == 2

        gene_locus = result["subjects"][0]
        assert gene_locus["subject"] == "7:19430034-19433113"
        assert "valueURI" not in gene_locus

        taxon = result["subjects"][1]
        assert taxon["valueURI"] == "http://purl.obolibrary.org/obo/NCBITaxon_10090"

    def test_legacy_is_related_to_is_normalized(self):
        """Legacy IsRelatedTo relation should be mapped to valid DataCite References."""
        fdf_json = json.dumps(
            {
                "relatedIdentifiers": [
                    {
                        "relatedIdentifier": "https://example.org/protocol.pdf",
                        "relatedIdentifierType": "URL",
                        "relationType": "IsRelatedTo",
                    }
                ]
            }
        )

        result = DataCiteConverter.fdf_to_datacite(fdf_json)
        assert "relatedIdentifiers" in result
        assert len(result["relatedIdentifiers"]) == 1
        assert result["relatedIdentifiers"][0]["relationType"] == "References"

    def test_structured_subjects_use_business_friendly_scheme_names(self):
        """Structured metadata should map to business-friendly scheme names."""
        fdf_json = json.dumps(
            {
                "genSymbol": "Apoe",
                "geneName": "apolipoprotein E",
                "geneAccessionId": "https://identifiers.org/ncbigene:11816",
                "geneChromosomeLocation": "7:19620966-19630842",
                "geneMutationType": "knockout",
                "alleleAccessionId": "https://identifiers.org/mgi:2181290",
                "alleleSymbol": "Apoetm1Unc",
                "speciesBackground": "C57BL/6J",
                "treatmentName": "Tamoxifen",
                "treatmentProtocol": "acute",
                "treatmentDesign": "50 mg/kg IP daily for 7 days",
            }
        )

        result = DataCiteConverter.fdf_to_datacite(fdf_json)
        schemes = {s.get("subjectScheme") for s in result.get("subjects", [])}

        assert "geneSymbol" in schemes
        assert "geneName" in schemes
        assert "geneAccessionId" in schemes
        assert "geneChromosomeLocation" in schemes
        assert "geneMutationType" in schemes
        assert "alleleAccessionId" in schemes
        assert "alleleSymbol" in schemes
        assert "speciesBackground" in schemes
        assert "treatmentName" in schemes
        assert "treatmentProtocol" in schemes
        assert "treatmentDesign" in schemes

    def test_legacy_structured_aliases_still_supported(self):
        """Legacy aliases should still be accepted to avoid breaking historical payloads."""
        fdf_json = json.dumps(
            {
                "geneSymbol": "Trp53",
                "mutation_type": "missense_variant",
                "geneticBackground": "BALB/c",
            }
        )

        result = DataCiteConverter.fdf_to_datacite(fdf_json)
        schemes = {s.get("subjectScheme") for s in result.get("subjects", [])}

        assert "geneSymbol" in schemes
        assert "geneMutationType" in schemes
        assert "speciesBackground" in schemes

    def test_subject_fallback_derives_missing_business_fields(self):
        """When only subject rows are present, derive expected business schemes."""
        fdf_json = json.dumps(
            {
                "subjects": [
                    {
                        "subject": "Gene: Apoe",
                        "subjectScheme": "geneAccessionId",
                        "valueURI": "https://identifiers.org/ncbigene:11816",
                    },
                    {
                        "subject": "Allele: Apoetm1Unc",
                        "subjectScheme": "alleleAccessionId",
                        "valueURI": "https://identifiers.org/mgi:2181290",
                    },
                    {
                        "subject": "tamoxifen citrate",
                        "subjectScheme": "ChEBI",
                        "valueURI": "http://purl.obolibrary.org/obo/CHEBI_9397",
                    },
                ],
                "treatmentProtocol": ["acute"],
                "treatmentDesign": ["50 mg/kg IP daily for 7 days"],
            }
        )

        result = DataCiteConverter.fdf_to_datacite(fdf_json)
        schemes = [s.get("subjectScheme") for s in result.get("subjects", [])]

        assert "geneSymbol" in schemes
        assert "alleleSymbol" in schemes
        assert "treatmentName" in schemes
        assert "treatmentProtocol" in schemes
        assert "treatmentDesign" in schemes

    def test_convert_to_extras_returns_empty_list_for_invalid_json(self):
        extras = convert_fdf_to_datacite_extras("{bad-json")
        assert extras == []

    def test_convert_to_extras_falls_back_to_string_when_json_dump_fails(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            datacite_converter_module.DataCiteConverter,
            "fdf_to_datacite",
            staticmethod(lambda _payload: {"publicationYear": "2026"}),
        )

        def _raise_type_error(_value):
            raise TypeError("boom")

        monkeypatch.setattr(datacite_converter_module.json, "dumps", _raise_type_error)

        extras = convert_fdf_to_datacite_extras("{}")

        assert extras == [{"key": "datacite.publicationYear", "value": "2026"}]
