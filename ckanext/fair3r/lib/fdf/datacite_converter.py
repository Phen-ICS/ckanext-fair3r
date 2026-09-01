"""
DataCite Metadata Converter

Converts FDF JSON (FAIR3R Dataset Form) to DataCite-compatible metadata
for DOI registration via ckanext-doi plugin.

The FDF JSON already contains DataCite-compliant structure (creators, subjects, etc.)
This converter extracts and formats it for ckanext-doi consumption.
"""

import json
import logging
import re
from typing import Any, ClassVar
from urllib.parse import urlparse

log = logging.getLogger(__name__)

_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*$")


class DataCiteConverter:
    """Convert FDF JSON to DataCite metadata format."""

    STRUCTURED_FIELD_ALIASES: ClassVar[dict[str, set[str]]] = {
        "geneSymbol": {"geneSymbol", "genSymbol", "GeneSymbol"},
        "geneName": {"geneName", "GeneName"},
        "geneAccessionId": {"geneAccessionId", "GeneAccessionID"},
        "geneChromosomeLocation": {
            "geneChromosomeLocation",
            "geneLocus",
            "GeneLocus",
        },
        "geneMutationType": {"geneMutationType", "mutation_type", "MutationType"},
        "alleleAccessionId": {"alleleAccessionId", "AlleleAccessionID"},
        "alleleSymbol": {"alleleSymbol", "AlleleSymbol"},
        "treatmentName": {"treatmentName", "Treatment"},
        "treatmentProtocol": {"treatmentProtocol", "TreatmentProtocol"},
        "treatmentDesign": {"treatmentDesign", "TreatmentDesign"},
        "speciesBackground": {"speciesBackground", "geneticBackground"},
    }

    INTERVENTION_LABELS: ClassVar[dict[str, str]] = {
        "GENE": "Genetic Modification",
        "CHEM": "Chemical / Pharmacological Treatment",
        "DIET": "Diet / Feeding Regimen",
        "DIS": "Disease Model",
        "ANAT": "Tissue / Organ of Interest",
    }

    VALID_RELATION_TYPES: ClassVar[set[str]] = {
        "IsCitedBy",
        "Cites",
        "IsSupplementTo",
        "IsSupplementedBy",
        "IsContinuedBy",
        "Continues",
        "IsDescribedBy",
        "Describes",
        "HasMetadata",
        "IsMetadataFor",
        "HasVersion",
        "IsVersionOf",
        "IsNewVersionOf",
        "IsPreviousVersionOf",
        "IsPartOf",
        "HasPart",
        "IsPublishedIn",
        "IsReferencedBy",
        "References",
        "IsDocumentedBy",
        "Documents",
        "IsCompiledBy",
        "Compiles",
        "IsVariantFormOf",
        "IsOriginalFormOf",
        "IsIdenticalTo",
        "IsReviewedBy",
        "Reviews",
        "IsDerivedFrom",
        "IsSourceOf",
        "IsRequiredBy",
        "Requires",
        "Obsoletes",
        "IsObsoletedBy",
    }

    @staticmethod
    def fdf_to_datacite(fdf_json_str: str) -> dict[str, Any]:
        """
        Convert FDF JSON to DataCite metadata dictionary.

        Args:
            fdf_json_str: JSON string from FDF form output

        Returns:
            Dict with DataCite-compliant metadata structure

        Raises:
            ValueError: If JSON parsing fails
        """
        try:
            fdf_data = json.loads(fdf_json_str)
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            log.error("Failed to parse FDF JSON for DataCite conversion: %s", e)
            raise ValueError(f"Invalid FDF JSON: {e}")

        datacite_metadata = {}

        # 1. Creators (required by DataCite)
        creators = DataCiteConverter._extract_creators(fdf_data)
        if creators:
            datacite_metadata["creators"] = creators

        # 2. Contributors (optional)
        contributors = DataCiteConverter._extract_contributors(fdf_data)
        if contributors:
            datacite_metadata["contributors"] = contributors

        # 3. Titles (usually from CKAN title field, but can include alternativeTitles)
        titles = DataCiteConverter._extract_titles(fdf_data)
        if titles:
            datacite_metadata["titles"] = titles

        # 4. Publication Year (required by DataCite)
        pub_year = fdf_data.get("publicationYear")
        if pub_year:
            datacite_metadata["publicationYear"] = str(pub_year)

        # 4b. Publisher details (optional but recommended)
        publisher_name = str(fdf_data.get("publisher") or "").strip()
        publisher_identifier = str(fdf_data.get("publisherIdentifier") or "").strip()
        if publisher_name:
            datacite_metadata["publisher"] = publisher_name
        if publisher_identifier:
            datacite_metadata["publisherIdentifier"] = publisher_identifier
            publisher_scheme, publisher_scheme_uri = (
                DataCiteConverter._infer_identifier_scheme(publisher_identifier)
            )
            if publisher_scheme:
                datacite_metadata["publisherIdentifierScheme"] = publisher_scheme
            if publisher_scheme_uri:
                datacite_metadata["schemeURI"] = publisher_scheme_uri

        # 5. Resource Type (required by DataCite)
        types = DataCiteConverter._extract_types(fdf_data)
        if types:
            datacite_metadata["types"] = types

        # 6. Subjects (biological annotations)
        subjects = DataCiteConverter._extract_subjects(fdf_data)
        if subjects:
            datacite_metadata["subjects"] = subjects

        # 7. Descriptions (abstract, methods, etc.)
        descriptions = DataCiteConverter._extract_descriptions(fdf_data)
        if descriptions:
            datacite_metadata["descriptions"] = descriptions

        # 8. Related identifiers (optional)
        related_identifiers = DataCiteConverter._extract_related_identifiers(fdf_data)
        if related_identifiers:
            datacite_metadata["relatedIdentifiers"] = related_identifiers

        log.info(
            "Converted FDF to DataCite metadata: %d creators, %d subjects, %d descriptions",
            len(creators),
            len(subjects),
            len(descriptions),
        )

        return datacite_metadata

    @staticmethod
    def _extract_creators(fdf_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract creators from FDF data.

        DataCite format:
        {
          "name": "Smith, John",
          "nameType": "Personal",
          "givenName": "John",
          "familyName": "Smith",
          "nameIdentifiers": [{
            "nameIdentifier": "https://orcid.org/0000-0001-2345-6789",
            "nameIdentifierScheme": "ORCID",
            "schemeURI": "https://orcid.org/"
          }],
          "affiliation": [{
            "affiliation": "University of Example",
            "affiliationIdentifier": "https://ror.org/123456",
            "affiliationIdentifierScheme": "ROR",
            "schemeURI": "https://ror.org/"
          }]
        }
        """
        creators_list = []

        for creator in fdf_data.get("creators", []):
            if not isinstance(creator, dict):
                continue

            name_type = creator.get("nameType", "Personal")

            if name_type == "Organizational":
                org_name = creator.get("organization_name", "").strip()
                if not org_name:
                    continue
                creator_entry = {
                    "nameType": "Organizational",
                    "name": org_name,
                }
                if creator.get("nameIdentifiers"):
                    creator_entry["nameIdentifiers"] = creator["nameIdentifiers"]
                if creator.get("contributorRoles"):
                    creator_entry["contributorRoles"] = creator["contributorRoles"]
                creators_list.append(creator_entry)
                continue

            # Personal creator
            given_name = creator.get("givenName", "").strip()
            family_name = creator.get("familyName", "").strip()

            if not given_name and not family_name:
                continue

            creator_entry = {"nameType": "Personal"}

            # Name (LastName, FirstName format for DataCite)
            if family_name and given_name:
                creator_entry["name"] = f"{family_name}, {given_name}"
                creator_entry["givenName"] = given_name
                creator_entry["familyName"] = family_name
            elif family_name:
                creator_entry["name"] = family_name
                creator_entry["familyName"] = family_name
            else:
                creator_entry["name"] = given_name
                creator_entry["givenName"] = given_name

            # Name Identifiers (ORCID)
            if creator.get("nameIdentifiers"):
                creator_entry["nameIdentifiers"] = creator["nameIdentifiers"]

            # Affiliation (pass through; assume upstream normalization)
            if creator.get("affiliation"):
                creator_entry["affiliation"] = creator["affiliation"]

            # CRediT contributor roles attached to the creator (DataCite 4.5+)
            if creator.get("contributorRoles"):
                creator_entry["contributorRoles"] = creator["contributorRoles"]

            creators_list.append(creator_entry)

        return creators_list

    @staticmethod
    def _extract_contributors(fdf_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract contributors from FDF data.

        Contributors are stored independently from Creators (no automatic
        derivation). FDF stores contributors with their own contributorType
        and optional CRediT roles. DataCite requires `name` and
        `contributorType` to be present.
        """
        contributors_list: list[dict[str, Any]] = []

        for contrib in fdf_data.get("contributors", []):
            if not isinstance(contrib, dict):
                continue

            normalized = dict(contrib)
            given_name = str(normalized.get("givenName") or "").strip()
            family_name = str(normalized.get("familyName") or "").strip()
            explicit_name = str(normalized.get("name") or "").strip()
            name_type = str(normalized.get("nameType") or "").strip()

            if not explicit_name:
                if family_name and given_name:
                    explicit_name = f"{family_name}, {given_name}"
                elif family_name:
                    explicit_name = family_name
                elif given_name:
                    explicit_name = given_name

            # For manual form entries, organization_name may be emitted
            # instead of DataCite name.
            if not explicit_name:
                organization_name = str(
                    normalized.get("organization_name") or ""
                ).strip()
                if organization_name:
                    explicit_name = organization_name
                    if not name_type:
                        name_type = "Organizational"

            contributor_type = str(normalized.get("contributorType") or "").strip()

            # DataCite requires contributorName and contributorType when a contributor is present.
            if not explicit_name or not contributor_type:
                continue

            normalized["name"] = explicit_name
            if name_type in {"Personal", "Organizational"}:
                normalized["nameType"] = name_type
            # Drop legacy `source` marker from datasets that pre-date the
            # Creator/Contributor disconnect; it is no longer used downstream.
            normalized.pop("source", None)
            contributors_list.append(normalized)

        return contributors_list

    @staticmethod
    def _extract_titles(fdf_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract titles (alternative titles) from FDF data.

        Main title comes from CKAN's title field.
        FDF may contain alternativeTitles in the titles array.
        """
        titles_list = []

        for title_obj in fdf_data.get("titles", []):
            if not isinstance(title_obj, dict):
                continue

            title_text = title_obj.get("title", "").strip()
            if not title_text:
                continue

            titles_list.append(
                {
                    "title": title_text,
                    "titleType": title_obj.get("titleType", "AlternativeTitle"),
                }
            )

        return titles_list

    @staticmethod
    def _extract_types(fdf_data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract resource type from FDF data.

        DataCite format:
        {
          "resourceType": "Dataset",
          "resourceTypeGeneral": "Dataset"
        }
        """
        types_list = fdf_data.get("types", [])

        if types_list and isinstance(types_list, list) and len(types_list) > 0:
            first_type = types_list[0]
            if isinstance(first_type, dict):
                return {
                    "resourceType": first_type.get("resourceType", "Dataset"),
                    "resourceTypeGeneral": first_type.get(
                        "resourceTypeGeneral", "Dataset"
                    ),
                }

        # Default fallback
        return {"resourceType": "Dataset", "resourceTypeGeneral": "Dataset"}

    @staticmethod
    def _extract_subjects(fdf_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract subjects from FDF data.

        FDF stores biological annotations as subjects with:
        - subject: text label (e.g., "Mus musculus", "Gene: Apoe")
        - subjectScheme: vocabulary scheme (NCBITaxon, ChEBI, DOID, etc.)
        - valueURI: persistent identifier URI
        - schemeURI: base URI for the scheme

        DataCite format:
        {
          "subject": "Mus musculus",
          "subjectScheme": "NCBITaxon",
          "valueURI": "http://purl.obolibrary.org/obo/NCBITaxon_10090",
          "schemeURI": "http://purl.obolibrary.org/obo/"
        }
        """
        subjects_list = []

        for subj in fdf_data.get("subjects", []):
            if not isinstance(subj, dict):
                continue

            subject_text = subj.get("subject", "").strip()
            subject_scheme = str(subj.get("subjectScheme") or "").strip()
            subject_text = DataCiteConverter._normalize_subject_text(
                subject_text,
                subject_scheme,
            )
            if not subject_text:
                continue

            subject_entry = {"subject": subject_text}

            # Add scheme information if present
            if subject_scheme:
                subject_entry["subjectScheme"] = subject_scheme

            value_uri = str(subj.get("valueURI") or "").strip()
            if value_uri:
                if DataCiteConverter._is_valid_datacite_uri(value_uri):
                    subject_entry["valueURI"] = value_uri
                else:
                    log.warning(
                        "Dropping invalid subject valueURI for DataCite: %s",
                        value_uri,
                    )

            scheme_uri = str(subj.get("schemeURI") or "").strip()
            if scheme_uri:
                if DataCiteConverter._is_valid_datacite_uri(scheme_uri):
                    subject_entry["schemeURI"] = scheme_uri
                else:
                    log.warning(
                        "Dropping invalid subject schemeURI for DataCite: %s",
                        scheme_uri,
                    )

            subjects_list.append(subject_entry)

        DataCiteConverter._append_structured_subjects(fdf_data, subjects_list)

        # Deduplicate while preserving order.
        deduped_subjects = []
        seen = set()
        for subject in subjects_list:
            key = (
                str(subject.get("subject") or "").strip().lower(),
                str(subject.get("subjectScheme") or "").strip().lower(),
                str(subject.get("valueURI") or "").strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped_subjects.append(subject)

        return deduped_subjects

    @staticmethod
    def _append_structured_subjects(
        fdf_data: dict[str, Any], subjects_list: list[dict[str, Any]]
    ) -> None:
        """Append normalized subjects from structured FDF keys as fallback data."""

        def _as_list(value: Any) -> list[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            text = str(value).strip()
            return [text] if text else []

        def _append_subject(
            label: str, scheme: str, value_uri: str | None = None
        ) -> None:
            if not label:
                return
            entry: dict[str, Any] = {
                "subject": DataCiteConverter._normalize_subject_text(label, scheme),
                "subjectScheme": scheme,
            }
            if value_uri and DataCiteConverter._is_valid_datacite_uri(value_uri):
                entry["valueURI"] = value_uri
            subjects_list.append(entry)

        def _has_existing_scheme(*schemes: str) -> bool:
            for subject in subjects_list:
                if not isinstance(subject, dict):
                    continue
                subject_scheme = str(subject.get("subjectScheme") or "").strip()
                if subject_scheme in schemes:
                    return True
            return False

        def _as_list_from_aliases(*keys: str) -> list[str]:
            values: list[str] = []
            for key in keys:
                values.extend(_as_list(fdf_data.get(key)))

            # dedupe while preserving order
            deduped: list[str] = []
            seen: set = set()
            for value in values:
                lowered = value.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                deduped.append(value)
            return deduped

        def _as_list_from_subjects(
            schemes: list[str], prefix: str | None = None
        ) -> list[str]:
            values: list[str] = []
            for subject in fdf_data.get("subjects", []):
                if not isinstance(subject, dict):
                    continue

                subject_scheme = str(subject.get("subjectScheme") or "").strip()
                if subject_scheme not in schemes:
                    continue

                label = str(subject.get("subject") or "").strip()
                if not label:
                    continue

                if prefix and label.lower().startswith(prefix.lower()):
                    label = label[len(prefix) :].strip()

                if label:
                    values.append(label)

            # dedupe while preserving order
            deduped: list[str] = []
            seen: set = set()
            for value in values:
                lowered = value.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                deduped.append(value)
            return deduped

        # Genes
        if not _has_existing_scheme("geneSymbol", "GeneSymbol"):
            gene_symbol_values = _as_list_from_aliases("geneSymbol", "genSymbol")
            if not gene_symbol_values:
                gene_symbol_values = _as_list_from_subjects(
                    ["geneAccessionId", "GeneID"], prefix="Gene:"
                )
            for value in gene_symbol_values:
                _append_subject(value, "geneSymbol")

        if not _has_existing_scheme("geneName", "GeneName"):
            for value in _as_list_from_aliases("geneName"):
                _append_subject(value, "geneName")

        if not _has_existing_scheme("geneAccessionId", "GeneAccessionID", "GeneID"):
            for value in _as_list_from_aliases("geneAccessionId"):
                if DataCiteConverter._is_valid_datacite_uri(value):
                    _append_subject(value, "geneAccessionId", value)
                else:
                    _append_subject(value, "geneAccessionId")

        if not _has_existing_scheme("geneChromosomeLocation", "GeneLocus"):
            for value in _as_list_from_aliases("geneChromosomeLocation", "geneLocus"):
                _append_subject(value, "geneChromosomeLocation")

        if not _has_existing_scheme("geneMutationType", "MutationType"):
            mutation_values = _as_list_from_aliases("geneMutationType", "mutation_type")
            for value in mutation_values:
                _append_subject(value, "geneMutationType")

        if not _has_existing_scheme(
            "alleleAccessionId", "AlleleAccessionID", "AlleleID"
        ):
            for value in _as_list_from_aliases("alleleAccessionId"):
                if DataCiteConverter._is_valid_datacite_uri(value):
                    _append_subject(value, "alleleAccessionId", value)
                else:
                    _append_subject(value, "alleleAccessionId")

        if not _has_existing_scheme("alleleSymbol", "AlleleSymbol"):
            allele_symbol_values = _as_list_from_aliases("alleleSymbol")
            if not allele_symbol_values:
                allele_symbol_values = _as_list_from_subjects(
                    ["alleleAccessionId", "AlleleID"], prefix="Allele:"
                )
            for value in allele_symbol_values:
                _append_subject(value, "alleleSymbol")

        if not _has_existing_scheme("speciesBackground", "Strain"):
            species_values = _as_list_from_aliases(
                "speciesBackground", "geneticBackground"
            )
            if not species_values:
                species_values = _as_list_from_subjects(
                    ["speciesBackground", "Strain"], prefix="Strain:"
                )
            for value in species_values:
                _append_subject(value, "speciesBackground")

        # Treatments / pharmacology
        if not _has_existing_scheme("treatmentName", "Treatment"):
            treatment_name_values = _as_list_from_aliases("treatmentName")
            if not treatment_name_values:
                treatment_name_values = _as_list_from_subjects(["ChEBI", "Treatment"])
            for value in treatment_name_values:
                _append_subject(value, "treatmentName")

        if not _has_existing_scheme("treatmentProtocol", "TreatmentProtocol"):
            for value in _as_list_from_aliases("treatmentProtocol"):
                _append_subject(value, "treatmentProtocol")

        if not _has_existing_scheme("treatmentDesign", "TreatmentDesign"):
            for value in _as_list_from_aliases("treatmentDesign"):
                _append_subject(value, "treatmentDesign")

    @staticmethod
    def _normalize_subject_text(subject: str, scheme: str) -> str:
        """Normalize subject labels and strip UI prefixes for XML subject values."""
        text = str(subject or "").strip()
        if not text:
            return ""

        scheme_name = str(scheme or "").strip()
        prefix_by_scheme = {
            "geneAccessionId": "Gene:",
            "GeneID": "Gene:",
            "alleleAccessionId": "Allele:",
            "AlleleID": "Allele:",
            "geneChromosomeLocation": "Gene locus:",
            "GeneLocus": "Gene locus:",
            "speciesBackground": "Strain:",
            "xenopusStrainLine": "Strain:",
            "Strain": "Strain:",
            "lineType": "Line type:",
            "geneMutationType": "Mutation type:",
            "MutationType": "Mutation type:",
            "TransgeneOrigin": "Transgene origin:",
        }
        prefix = prefix_by_scheme.get(scheme_name)
        if prefix and text.lower().startswith(prefix.lower()):
            text = text[len(prefix) :].strip()

        return text

    @staticmethod
    def _extract_related_identifiers(fdf_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract related identifiers in DataCite-compatible format."""
        results: list[dict[str, Any]] = []

        source_items = fdf_data.get("relatedIdentifiers")
        if not isinstance(source_items, list):
            source_items = fdf_data.get("related_identifiers")
        if not isinstance(source_items, list):
            source_items = []

        for item in source_items:
            if not isinstance(item, dict):
                continue

            rid = str(
                item.get("relatedIdentifier") or item.get("related_identifier") or ""
            ).strip()
            if not rid:
                continue

            relation_type = str(
                item.get("relationType")
                or item.get("relatedRelationType")
                or item.get("related_relation_type")
                or "References"
            ).strip()
            if relation_type == "IsRelatedTo":
                relation_type = "References"
            if relation_type not in DataCiteConverter.VALID_RELATION_TYPES:
                log.warning(
                    "Invalid DataCite relationType '%s'; using 'References' instead",
                    relation_type,
                )
                relation_type = "References"
            identifier_type = str(
                item.get("relatedIdentifierType")
                or item.get("related_identifier_type")
                or "URL"
            ).strip()

            results.append(
                {
                    "relatedIdentifier": rid,
                    "relatedIdentifierType": identifier_type,
                    "relationType": relation_type,
                }
            )

        return results

    @staticmethod
    def _infer_identifier_scheme(
        identifier: str,
    ) -> tuple[str | None, str | None]:
        """Infer scheme and scheme URI for common identifiers."""
        identifier = str(identifier or "").strip()
        if not identifier:
            return None, None

        lower = identifier.lower()
        if "ror.org" in lower:
            return "ROR", "https://ror.org/"
        if "orcid.org" in lower:
            return "ORCID", "https://orcid.org/"
        if lower.startswith("doi:") or "doi.org" in lower:
            return "DOI", "https://doi.org/"

        return None, None

    @staticmethod
    def _is_valid_datacite_uri(value: str) -> bool:
        """Return True when value looks like a valid absolute URI for DataCite anyURI fields."""
        if not value or any(ch.isspace() for ch in value):
            return False

        parsed = urlparse(value)
        if not parsed.scheme:
            return False

        return bool(_URI_SCHEME_RE.match(parsed.scheme))

    @staticmethod
    def _extract_descriptions(fdf_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract descriptions from FDF data.

        DataCite format:
        {
          "description": "This dataset contains...",
          "descriptionType": "Abstract"
        }
        Order: Abstract/Methods first (human content), then TechnicalInfo (metadata summary)
        """
        descriptions_list = []

        # First add existing descriptions (Abstract, Methods, etc.) - human content
        for desc in fdf_data.get("descriptions", []):
            if not isinstance(desc, dict):
                continue

            desc_text = desc.get("description", "").strip()
            if not desc_text:
                continue

            descriptions_list.append(
                {
                    "description": desc_text,
                    "descriptionType": desc.get("descriptionType", "Abstract"),
                }
            )

        # Then add the FDF form summary as Methods to preserve study metadata in XML.
        summary_text = DataCiteConverter._build_fdf_summary_description(fdf_data)
        if summary_text:
            descriptions_list.append(
                {"description": summary_text, "descriptionType": "Methods"}
            )

        return descriptions_list

    @staticmethod
    def _build_fdf_summary_description(fdf_data: dict[str, Any]) -> str | None:
        """Build a concise, human-readable summary from FDF form content."""
        lines = ["FAIR3R form summary"]

        publication_year = fdf_data.get("publicationYear")
        if publication_year:
            lines.append(f"Publication year: {publication_year}")

        resource_type = DataCiteConverter._extract_resource_type_label(fdf_data)
        if resource_type:
            lines.append(f"Resource type: {resource_type}")

        creator_names = DataCiteConverter._extract_creator_names(fdf_data)
        if creator_names:
            lines.append(f"Creators: {'; '.join(creator_names)}")

        contributor_names = DataCiteConverter._extract_contributor_summaries(fdf_data)
        if contributor_names:
            lines.append(f"Contributors: {'; '.join(contributor_names)}")

        organisms = DataCiteConverter._collect_subject_values_by_scheme(
            fdf_data,
            target_schemes={"NCBITaxon"},
        )
        if organisms:
            lines.append(f"Organisms: {', '.join(organisms)}")

        strains = DataCiteConverter._collect_subject_values_by_prefix(
            fdf_data, "Strain:"
        )
        if strains:
            lines.append(f"Strains: {', '.join(strains)}")

        genes = DataCiteConverter._collect_subject_values_by_prefix(fdf_data, "Gene:")
        if genes:
            lines.append(f"Genes: {', '.join(genes)}")

        alleles = DataCiteConverter._collect_subject_values_by_prefix(
            fdf_data, "Allele:"
        )
        if alleles:
            lines.append(f"Alleles: {', '.join(alleles)}")

        gene_loci = DataCiteConverter._collect_subject_values_by_prefix(
            fdf_data, "Gene locus:"
        )
        if gene_loci:
            lines.append(f"Gene chromosome location: {', '.join(gene_loci)}")

        treatment_summaries = DataCiteConverter._extract_treatment_summaries(fdf_data)
        if treatment_summaries:
            lines.append(f"Treatments: {'; '.join(treatment_summaries)}")

        chemicals = DataCiteConverter._collect_subject_values_by_scheme(
            fdf_data,
            target_schemes={"ChEBI"},
        )
        if chemicals:
            lines.append(f"Chemicals: {', '.join(chemicals)}")

        diets = DataCiteConverter._collect_subject_values_by_scheme(
            fdf_data,
            target_schemes={"EFO"},
            exclude_prefixes=["Strain:"],
        )
        if diets:
            lines.append(f"Diets: {', '.join(diets)}")

        diseases = DataCiteConverter._collect_subject_values_by_scheme(
            fdf_data,
            target_schemes={"DOID"},
        )
        if diseases:
            lines.append(f"Disease models: {', '.join(diseases)}")

        anatomy = DataCiteConverter._collect_subject_values_by_scheme(
            fdf_data,
            target_schemes={"UBERON"},
        )
        if anatomy:
            lines.append(f"Tissues / organs: {', '.join(anatomy)}")

        interventions = fdf_data.get("experimentalInterventions", [])
        if isinstance(interventions, list):
            cleaned_interventions = [
                DataCiteConverter.INTERVENTION_LABELS.get(
                    str(item).strip(), str(item).strip()
                )
                for item in interventions
                if str(item).strip()
            ]
            if cleaned_interventions:
                lines.append(
                    f"Experimental interventions: {', '.join(cleaned_interventions)}"
                )

        # Keep the summary only if we have meaningful content beyond the header.
        if len(lines) <= 1:
            return None

        return "\n".join(lines)

    @staticmethod
    def _extract_treatment_summaries(fdf_data: dict[str, Any]) -> list[str]:
        """Build treatment summaries from chemical subjects and treatment detail arrays."""
        treatment_names = DataCiteConverter._collect_subject_values_by_scheme(
            fdf_data,
            target_schemes={"ChEBI"},
        )

        protocols = fdf_data.get("treatmentProtocol", [])
        designs = fdf_data.get("treatmentDesign", [])

        arrays = [
            treatment_names if isinstance(treatment_names, list) else [],
            protocols if isinstance(protocols, list) else [],
            designs if isinstance(designs, list) else [],
        ]

        max_len = max((len(arr) for arr in arrays), default=0)
        if max_len == 0:
            return []

        summaries: list[str] = []
        for idx in range(max_len):
            name = (
                str(treatment_names[idx]).strip() if idx < len(treatment_names) else ""
            )
            protocol = str(protocols[idx]).strip() if idx < len(protocols) else ""
            design = str(designs[idx]).strip() if idx < len(designs) else ""

            parts: list[str] = []
            if name:
                parts.append(name)
            if protocol:
                parts.append(f"protocol={protocol}")
            if design:
                parts.append(f"design={design}")

            if parts:
                summaries.append(" | ".join(parts))

        return summaries

    @staticmethod
    def _extract_resource_type_label(fdf_data: dict[str, Any]) -> str | None:
        """Return the first available resource type label from FDF types."""
        types = fdf_data.get("types", [])
        if not isinstance(types, list) or not types:
            return None

        first_type = types[0]
        if not isinstance(first_type, dict):
            return None

        value = first_type.get("resourceType") or first_type.get("resourceTypeGeneral")
        if value is None:
            return None

        value_str = str(value).strip()
        return value_str or None

    @staticmethod
    def _extract_creator_names(fdf_data: dict[str, Any]) -> list[str]:
        """Extract human-readable creator names from FDF data."""
        names: list[str] = []
        seen: set = set()
        for creator in fdf_data.get("creators", []):
            if not isinstance(creator, dict):
                continue
            given = str(creator.get("givenName") or "").strip()
            family = str(creator.get("familyName") or "").strip()
            label = (
                f"{given} {family}".strip()
                if (given or family)
                else str(creator.get("name") or "").strip()
            )
            if label and label.lower() not in seen:
                seen.add(label.lower())
                names.append(label)
        return names

    @staticmethod
    def _extract_contributor_summaries(fdf_data: dict[str, Any]) -> list[str]:
        """Extract contributor names with optional CRediT roles from FDF data.

        Contributors are now independent of Creators, so no matching/merging
        is performed here.
        """
        summary_map: dict[tuple, dict[str, Any]] = {}
        for contributor in fdf_data.get("contributors", []):
            if not isinstance(contributor, dict):
                continue
            name = DataCiteConverter._contributor_display_name(contributor)
            if not name:
                continue
            identity = DataCiteConverter._person_identity_key(contributor)
            roles = [
                str(r.get("contributorRole") or "").strip()
                for r in (contributor.get("contributorRoles") or [])
                if isinstance(r, dict) and str(r.get("contributorRole") or "").strip()
            ]
            entry = summary_map.setdefault(identity, {"name": name, "roles": []})
            if entry["name"] in {"", None}:
                entry["name"] = name
            for role in roles:
                if role and role.lower() not in {r.lower() for r in entry["roles"]}:
                    entry["roles"].append(role)

        summaries: list[str] = []
        for entry in summary_map.values():
            summary = (
                f"{entry['name']} ({', '.join(entry['roles'])})"
                if entry["roles"]
                else entry["name"]
            )
            if summary:
                summaries.append(summary)
        return summaries

    @staticmethod
    def _contributor_display_name(contributor: dict[str, Any]) -> str:
        family = str(contributor.get("familyName") or "").strip()
        given = str(contributor.get("givenName") or "").strip()
        if family and given:
            return f"{family}, {given}"
        if family:
            return family
        if given:
            return given
        explicit_name = str(
            contributor.get("name") or contributor.get("organization_name") or ""
        ).strip()
        normalized_name_type = DataCiteConverter._normalized_name_type(
            contributor.get("nameType")
        )
        if normalized_name_type == "Organizational":
            return explicit_name
        if "," in explicit_name:
            left, right = explicit_name.split(",", 1)
            left = left.strip()
            right = right.strip()
            return f"{left}, {right}" if left and right else explicit_name
        tokens = [token for token in explicit_name.split() if token]
        if len(tokens) > 1:
            return f"{tokens[-1]}, {' '.join(tokens[:-1])}"
        return explicit_name

    @staticmethod
    def _normalized_name_type(name_type: Any) -> str:
        normalized = str(name_type or "").strip().lower()
        if normalized == "personal":
            return "Personal"
        if normalized == "organizational":
            return "Organizational"
        return ""

    @staticmethod
    def _person_identity_key(person: dict[str, Any]) -> tuple:
        normalized_name_type = DataCiteConverter._normalized_name_type(
            person.get("nameType")
        )
        name_type = normalized_name_type.lower()
        family = (
            str(person.get("familyName") or person.get("family_name") or "")
            .strip()
            .lower()
        )
        given = (
            str(person.get("givenName") or person.get("given_name") or "")
            .strip()
            .lower()
        )
        explicit_name = str(
            person.get("name")
            or person.get("full_name")
            or person.get("organization_name")
            or ""
        ).strip()

        if family or given:
            return (name_type or "personal", family, given)

        if "," in explicit_name:
            left, right = explicit_name.split(",", 1)
            return (
                name_type or "personal",
                left.strip().lower(),
                right.strip().lower(),
            )

        tokens = [token for token in explicit_name.split() if token]
        if (name_type == "organizational") or len(tokens) <= 1:
            return (name_type or "organizational", explicit_name.lower(), "")

        return (
            name_type or "personal",
            tokens[-1].lower(),
            " ".join(tokens[:-1]).lower(),
        )

    @staticmethod
    def _collect_subject_values_by_scheme(
        fdf_data: dict[str, Any],
        target_schemes: set,
        exclude_prefixes: list[str] | None = None,
    ) -> list[str]:
        """Collect unique subject labels for the given subject schemes."""
        values: list[str] = []
        seen: set = set()
        for subject in fdf_data.get("subjects", []):
            if not isinstance(subject, dict):
                continue
            if str(subject.get("subjectScheme") or "").strip() not in target_schemes:
                continue
            label = DataCiteConverter._extract_display_label(subject)
            if not label:
                continue
            if exclude_prefixes and any(
                label.lower().startswith(p.lower()) for p in exclude_prefixes
            ):
                continue
            if label.lower() not in seen:
                seen.add(label.lower())
                values.append(label)
        return values

    @staticmethod
    def _collect_subject_values_by_prefix(
        fdf_data: dict[str, Any], prefix: str
    ) -> list[str]:
        """Collect unique subject labels matching a prefix like 'Gene:' or 'Strain:'."""
        values: list[str] = []
        seen: set = set()
        prefix_lower = prefix.lower()
        for subject in fdf_data.get("subjects", []):
            if not isinstance(subject, dict):
                continue
            raw_label = str(subject.get("subject") or "").strip()
            if not raw_label.lower().startswith(prefix_lower):
                continue
            cleaned = raw_label[
                len(prefix) :
            ].strip() or DataCiteConverter._extract_display_label(subject)
            cleaned = DataCiteConverter._compact_identifier_label(cleaned)
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                values.append(cleaned)
        return values

    @staticmethod
    def _extract_display_label(subject: dict[str, Any]) -> str:
        """Return the most human-readable label available for a subject entry."""
        raw_label = str(subject.get("subject") or "").strip()
        if raw_label:
            return DataCiteConverter._compact_identifier_label(raw_label)

        value_uri = str(subject.get("valueURI") or "").strip()
        if value_uri:
            return DataCiteConverter._compact_identifier_label(value_uri)

        return ""

    @staticmethod
    def _compact_identifier_label(value: str) -> str:
        """Compact common ontology / identifier URIs into shorter human-readable labels."""
        text = str(value or "").strip()
        if not text:
            return ""

        if text.lower().startswith("gene:"):
            prefix, remainder = text.split(":", 1)
            compacted = DataCiteConverter._compact_identifier_label(remainder)
            return f"{prefix}: {compacted}" if compacted else prefix

        if text.lower().startswith("strain:"):
            prefix, remainder = text.split(":", 1)
            compacted = DataCiteConverter._compact_identifier_label(remainder)
            return f"{prefix}: {compacted}" if compacted else prefix

        patterns = [
            r"https?://identifiers\.org/([^\s/]+:[^\s/]+)$",
            r"https?://www\.ebi\.ac\.uk/efo/(EFO_[0-9]+)$",
            r"https?://purl\.obolibrary\.org/obo/([A-Za-z]+_[0-9]+)$",
            r"https?://.*?/([A-Za-z]+_[0-9]+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return text


def convert_fdf_to_datacite_extras(fdf_json_str: str) -> list[dict[str, str]]:
    """
    Convert FDF JSON to CKAN extras format with DataCite fields.

    This creates additional extras entries that ckanext-doi can read
    to populate DataCite metadata during DOI minting.

    Args:
        fdf_json_str: JSON string from FDF form output

    Returns:
        List of dicts with 'key' and 'value' for CKAN extras

    Example return:
        [
            {'key': 'datacite.creators', 'value': '[{"name": "Smith, John", ...}]'},
            {'key': 'datacite.subjects', 'value': '[{"subject": "Mus musculus", ...}]'},
            ...
        ]
    """
    try:
        datacite_metadata = DataCiteConverter.fdf_to_datacite(fdf_json_str)
    except ValueError as e:
        log.error("Failed to convert FDF to DataCite metadata: %s", e)
        return []

    # Normalize creators/contributors for ckanext-doi's xml_utils.create_contributor(**kwargs)
    # expected signature (full_name, family_name, given_name, is_org, contributor_type,
    # affiliations, identifiers). This avoids passing DataCite XML keys (e.g. nameType).
    creators = datacite_metadata.get("creators")
    if isinstance(creators, list):
        normalized_creators = []
        for creator in creators:
            normalized = _normalize_for_ckanext_doi_contributor(creator)
            if normalized:
                normalized_creators.append(normalized)
        normalized_creators = _dedupe_normalized_people(normalized_creators)
        if normalized_creators:
            datacite_metadata["creators"] = normalized_creators

    contributors = datacite_metadata.get("contributors")
    if isinstance(contributors, list):
        normalized_contributors = []
        for contributor in contributors:
            normalized = _normalize_for_ckanext_doi_contributor(
                contributor, default_contributor_type="Researcher"
            )
            if normalized:
                normalized_contributors.append(normalized)
        normalized_contributors = _dedupe_normalized_people(
            normalized_contributors,
            include_contributor_type=True,
        )
        if normalized_contributors:
            datacite_metadata["contributors"] = normalized_contributors

    extras = []

    # Convert each DataCite field to an extra
    # Sanitize and filter out empty values that would fail DataCite validation
    for key, value in datacite_metadata.items():
        # Skip None values and empty lists/dicts
        if value is None:
            continue

        # For lists, filter out empty items and skip if result is empty
        if isinstance(value, list):
            value = _filter_list_for_datacite(value)
            if not value:
                log.debug(f"Skipping empty list for {key}")
                continue

        # For dicts, skip if empty
        if isinstance(value, dict) and not value:
            continue

        # Append as CKAN extra with datacite.<key> and JSON string value
        try:
            extras.append({"key": f"datacite.{key}", "value": json.dumps(value)})
        except (TypeError, ValueError, json.JSONDecodeError):
            # Fallback: stringify value
            extras.append({"key": f"datacite.{key}", "value": str(value)})

    return extras


def _filter_list_for_datacite(items: list[Any]) -> list[Any]:
    """
    Filter a list to remove empty items (empty strings, None, empty dicts, etc.)
    that would fail DataCite XML validation.
    """
    filtered = []
    for item in items:
        if item is None:
            continue

        # For dict items (like creator entries)
        if isinstance(item, dict):
            # Filter out None/empty values from dict items
            cleaned_item = {}
            for k, v in item.items():
                if v is None:
                    continue
                if isinstance(v, str) and not v.strip():
                    continue
                if isinstance(v, list) and not v:
                    continue
                if isinstance(v, dict) and not v:
                    continue
                # For nested lists (like nameIdentifiers), apply same filter
                if isinstance(v, list):
                    v = _filter_list_for_datacite(v)
                    if not v:
                        continue
                cleaned_item[k] = v

            # Only include dict if it still has content
            if cleaned_item:
                filtered.append(cleaned_item)

        # For string items
        elif isinstance(item, str):
            if item.strip():
                filtered.append(item.strip())

        # For other types, include as-is
        else:
            filtered.append(item)

    return filtered


def _s(value) -> str | None:
    """Strip a string value or return None if empty/non-string."""
    return value.strip() or None if isinstance(value, str) else value


def _normalize_for_ckanext_doi_contributor(
    entry: dict[str, Any],
    default_contributor_type: str | None = None,
) -> dict[str, Any] | None:
    """Convert a DataCite-style contributor object to ckanext-doi contributor kwargs."""
    if not isinstance(entry, dict):
        return None

    is_org = str(entry.get("nameType", "")).lower() == "organizational"
    full_name = _s(entry.get("name") or entry.get("full_name"))
    family_name = _s(entry.get("familyName") or entry.get("family_name"))
    given_name = _s(entry.get("givenName") or entry.get("given_name"))

    if not full_name:
        full_name = (
            f"{family_name}, {given_name}"
            if family_name and given_name
            else family_name or given_name
        )
    if not full_name:
        return None

    normalized: dict[str, Any] = {"full_name": full_name, "is_org": is_org}
    if family_name:
        normalized["family_name"] = family_name
    if given_name:
        normalized["given_name"] = given_name

    contributor_type = (
        entry.get("contributorType")
        or entry.get("contributor_type")
        or default_contributor_type
    )
    if contributor_type:
        normalized["contributor_type"] = contributor_type

    affiliations = (
        entry.get("affiliations")
        if entry.get("affiliations") is not None
        else entry.get("affiliation")
    )
    if affiliations is not None:
        if not isinstance(affiliations, list):
            affiliations = [affiliations]
        aff_values = []
        aff_objects = []
        for a in affiliations:
            if isinstance(a, dict):
                name = str(a.get("affiliation", "") or a.get("name", "")).strip()
                aff_id = (
                    a.get("affiliationIdentifier")
                    or a.get("affiliation_identifier")
                    or ""
                ).strip() or None
                aff_scheme = (
                    a.get("affiliationIdentifierScheme")
                    or a.get("affiliation_scheme")
                    or ""
                ).strip() or None
                aff_scheme_uri = (
                    a.get("schemeURI")
                    or a.get("schemeUri")
                    or a.get("scheme_uri")
                    or ""
                ).strip() or None
                if name:
                    aff_values.append(name)
                if aff_id or name:
                    aff_objects.append(
                        {
                            "name": name,
                            "affiliationIdentifier": aff_id,
                            "affiliationIdentifierScheme": aff_scheme,
                            "schemeURI": aff_scheme_uri,
                        }
                    )
            else:
                name = str(a).strip()
                if name:
                    aff_values.append(name)
                    aff_objects.append({"name": name})
        if aff_values:
            normalized["affiliations"] = aff_values
        if aff_objects:
            normalized["affiliation_objects"] = aff_objects

    identifiers = (
        entry.get("identifiers")
        if entry.get("identifiers") is not None
        else entry.get("nameIdentifiers")
    )
    if identifiers is not None:
        if not isinstance(identifiers, list):
            identifiers = [identifiers]
        id_values = []
        for idf in identifiers:
            if not isinstance(idf, dict):
                continue
            id_val = _s(idf.get("identifier") or idf.get("nameIdentifier"))
            scheme = _s(idf.get("scheme") or idf.get("nameIdentifierScheme"))
            scheme_uri = _s(idf.get("scheme_uri") or idf.get("schemeURI"))
            if id_val and scheme:
                entry_dict: dict[str, str] = {"identifier": id_val, "scheme": scheme}
                if scheme_uri:
                    entry_dict["scheme_uri"] = scheme_uri
                id_values.append(entry_dict)
        if id_values:
            normalized["identifiers"] = id_values

    return normalized


def _dedupe_normalized_people(
    people: list[dict[str, Any]],
    include_contributor_type: bool = False,
) -> list[dict[str, Any]]:
    """Remove duplicate normalized people entries while preserving order."""
    deduped: list[dict[str, Any]] = []
    index_by_key: dict[tuple[str, bool, str | None], int] = {}

    def _identifier_tuple(id_obj: dict[str, Any]) -> tuple[str, str, str]:
        return (
            (id_obj.get("identifier") or "").strip().lower(),
            (id_obj.get("scheme") or "").strip().lower(),
            (id_obj.get("scheme_uri") or "").strip().lower(),
        )

    for person in people:
        if not isinstance(person, dict):
            continue

        name_key = (
            (person.get("full_name") or "").strip().lower(),
            bool(person.get("is_org")),
        )
        contrib_type = (
            (person.get("contributor_type") or "").strip().lower()
            if include_contributor_type
            else None
        )
        key = (name_key[0], name_key[1], contrib_type)

        if key in index_by_key:
            # merge into existing entry
            idx = index_by_key[key]
            existing = deduped[idx]

            # merge family/given names if missing
            for k in ("family_name", "given_name"):
                if not existing.get(k) and person.get(k):
                    existing[k] = person[k]

            # merge affiliations (strings)
            existing_affs = set(existing.get("affiliations") or [])
            new_affs = set(person.get("affiliations") or [])
            merged_affs = list(existing_affs.union(new_affs))
            if merged_affs:
                existing["affiliations"] = merged_affs

            # merge affiliation_objects
            def _aff_key(a: dict[str, Any]) -> tuple[str, str, str]:
                return (
                    (a.get("name") or "").strip().lower(),
                    (a.get("affiliationIdentifier") or "").strip().lower(),
                    (a.get("affiliationIdentifierScheme") or "").strip().lower(),
                )

            existing_objs = existing.get("affiliation_objects") or []
            new_objs = person.get("affiliation_objects") or []
            seen_objs = {_aff_key(a): a for a in existing_objs if isinstance(a, dict)}
            for a in new_objs:
                if not isinstance(a, dict):
                    continue
                ak = _aff_key(a)
                if ak not in seen_objs:
                    existing_objs.append(a)
                    seen_objs[ak] = a
            if existing_objs:
                existing["affiliation_objects"] = existing_objs

            # merge identifiers
            existing_ids = {
                _identifier_tuple(i): i
                for i in existing.get("identifiers") or []
                if isinstance(i, dict)
            }
            for i in person.get("identifiers") or []:
                if not isinstance(i, dict):
                    continue
                it = _identifier_tuple(i)
                if it not in existing_ids:
                    existing.setdefault("identifiers", []).append(i)
                    existing_ids[it] = i

            # prefer contributor_type if existing missing
            if (
                include_contributor_type
                and not existing.get("contributor_type")
                and person.get("contributor_type")
            ):
                existing["contributor_type"] = person.get("contributor_type")

        else:
            # new entry - normalize lists to avoid later duplicates
            if person.get("affiliations") and not isinstance(
                person.get("affiliations"), list
            ):
                person["affiliations"] = [person["affiliations"]]
            if person.get("identifiers") and not isinstance(
                person.get("identifiers"), list
            ):
                person["identifiers"] = [person["identifiers"]]
            index_by_key[key] = len(deduped)
            deduped.append(person)

    return deduped


def get_datacite_xml(fdf_json_str: str, title: str, publisher: str, doi: str) -> str:
    """
    Generate DataCite XML from FDF JSON.

    This can be used directly with DataCite API for DOI registration.

    Args:
        fdf_json_str: JSON string from FDF form output
        title: Dataset title (from CKAN)
        publisher: Publisher name (from CKAN config)
        doi: DOI identifier (e.g., "10.5281/zenodo.1234567")

    Returns:
        DataCite XML string (version 4.x)
    """
    try:
        datacite_metadata = DataCiteConverter.fdf_to_datacite(fdf_json_str)
    except ValueError as e:
        log.error("Failed to convert FDF to DataCite for XML generation: %s", e)
        return ""

    # Build DataCite XML 4.4
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<resource xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ')
    xml_parts.append('xmlns="http://datacite.org/schema/kernel-4" ')
    xml_parts.append('xsi:schemaLocation="http://datacite.org/schema/kernel-4 ')
    xml_parts.append('http://datacite.org/schema/meta/kernel-4.4/metadata.xsd">')

    # Identifier (DOI)
    xml_parts.append(f'  <identifier identifierType="DOI">{doi}</identifier>')

    # Creators
    if datacite_metadata.get("creators"):
        xml_parts.append("  <creators>")
        for creator in datacite_metadata["creators"]:
            xml_parts.append("    <creator>")
            xml_parts.append(
                f'      <creatorName nameType="{creator.get("nameType", "Personal")}">'
            )
            xml_parts.append(f"{_xml_escape(creator.get('name', ''))}</creatorName>")
            if creator.get("givenName"):
                xml_parts.append(
                    f"      <givenName>{_xml_escape(creator['givenName'])}</givenName>"
                )
            if creator.get("familyName"):
                xml_parts.append(
                    f"      <familyName>{_xml_escape(creator['familyName'])}</familyName>"
                )

            # Name Identifiers (ORCID)
            if creator.get("nameIdentifiers"):
                for name_id in creator["nameIdentifiers"]:
                    scheme = name_id.get("nameIdentifierScheme", "ORCID")
                    scheme_uri = name_id.get("schemeURI", "")
                    xml_parts.append(
                        f'      <nameIdentifier nameIdentifierScheme="{scheme}" schemeURI="{scheme_uri}">'
                    )
                    xml_parts.append(
                        f"{_xml_escape(name_id.get('nameIdentifier', ''))}</nameIdentifier>"
                    )

            # Affiliation
            if creator.get("affiliation"):
                for aff in creator["affiliation"]:
                    aff_id = aff.get("affiliationIdentifier", "")
                    aff_scheme = aff.get("affiliationIdentifierScheme", "")
                    aff_scheme_uri = aff.get("schemeURI", "")
                    xml_parts.append(
                        f'      <affiliation affiliationIdentifier="{aff_id}" '
                    )
                    xml_parts.append(
                        f'affiliationIdentifierScheme="{aff_scheme}" schemeURI="{aff_scheme_uri}">'
                    )
                    # affiliation object may use 'name' (DataCite JSON) or legacy 'affiliation'
                    aff_label = aff.get("name") or aff.get("affiliation") or ""
                    xml_parts.append(f"{_xml_escape(aff_label)}</affiliation>")

            xml_parts.append("    </creator>")
        xml_parts.append("  </creators>")

    # Titles
    xml_parts.append("  <titles>")
    xml_parts.append(f"    <title>{_xml_escape(title)}</title>")
    for alt_title in datacite_metadata.get("titles", []):
        title_type = alt_title.get("titleType", "AlternativeTitle")
        xml_parts.append(
            f'    <title titleType="{title_type}">{_xml_escape(alt_title.get("title", ""))}</title>'
        )
    xml_parts.append("  </titles>")

    # Publisher (prefer FDF value when available)
    xml_publisher = datacite_metadata.get("publisher") or publisher
    xml_parts.append(f"  <publisher>{_xml_escape(xml_publisher)}</publisher>")

    # Publication Year
    pub_year = datacite_metadata.get("publicationYear", "2026")
    xml_parts.append(f"  <publicationYear>{pub_year}</publicationYear>")

    # Resource Type
    types = datacite_metadata.get("types", {})
    resource_type = types.get("resourceType", "Dataset")
    resource_type_general = types.get("resourceTypeGeneral", "Dataset")
    xml_parts.append(
        f'  <resourceType resourceTypeGeneral="{resource_type_general}">{_xml_escape(resource_type)}</resourceType>'
    )

    # Subjects
    if datacite_metadata.get("subjects"):
        xml_parts.append("  <subjects>")
        for subj in datacite_metadata["subjects"]:
            scheme = subj.get("subjectScheme", "")
            scheme_uri = subj.get("schemeURI", "")
            value_uri = subj.get("valueURI", "")

            xml_parts.append(
                f'    <subject subjectScheme="{scheme}" schemeURI="{scheme_uri}" valueURI="{value_uri}">'
            )
            xml_parts.append(f"{_xml_escape(subj.get('subject', ''))}</subject>")
        xml_parts.append("  </subjects>")

    # Contributors
    if datacite_metadata.get("contributors"):
        xml_parts.append("  <contributors>")
        for contrib in datacite_metadata["contributors"]:
            contrib_type = contrib.get("contributorType", "Other")
            xml_parts.append(f'    <contributor contributorType="{contrib_type}">')
            xml_parts.append(
                f'      <contributorName nameType="{contrib.get("nameType", "Personal")}">'
            )
            xml_parts.append(
                f"{_xml_escape(contrib.get('name', ''))}</contributorName>"
            )

            # Contributor Roles (CRediT)
            if contrib.get("contributorRoles"):
                for role in contrib["contributorRoles"]:
                    xml_parts.append(
                        f'      <contributorRole contributorRoleScheme="{role.get("contributorRoleScheme", "CRediT")}">'
                    )
                    xml_parts.append(
                        f"{_xml_escape(role.get('contributorRole', ''))}</contributorRole>"
                    )

            xml_parts.append("    </contributor>")
        xml_parts.append("  </contributors>")

    # Descriptions
    if datacite_metadata.get("descriptions"):
        xml_parts.append("  <descriptions>")
        for desc in datacite_metadata["descriptions"]:
            desc_type = desc.get("descriptionType", "Abstract")
            xml_parts.append(f'    <description descriptionType="{desc_type}">')
            xml_parts.append(
                f"{_xml_escape(desc.get('description', ''))}</description>"
            )
        xml_parts.append("  </descriptions>")

    xml_parts.append("</resource>")

    return "\n".join(xml_parts)


def _xml_escape(text: str) -> str:
    """Escape special XML characters."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
