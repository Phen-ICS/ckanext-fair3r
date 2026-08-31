import json
import logging
import os
import re
from logging import getLogger
from typing import ClassVar

import ckan.lib.mailer as ckan_mailer
from ckan import plugins
from ckan.common import current_user, request
from ckan.lib.plugins import DefaultTranslation
from ckan.plugins import (
    toolkit,  # module containing toolkit functions, classes and exceptions for use by CKAN extensions.
)

from ckanext.doi.interfaces import IDoi  # type: ignore
from ckanext.fair3r import cli
from ckanext.fair3r.blueprints.account_request import account_request
from ckanext.fair3r.blueprints.activity_guard import activity_guard
from ckanext.fair3r.blueprints.dataset_choice import dataset_choice
from ckanext.fair3r.blueprints.download_all import download_all
from ckanext.fair3r.blueprints.fdf import fdf
from ckanext.fair3r.blueprints.sitemap import sitemap
from ckanext.fair3r.blueprints.standard_creation import standard_creation
from ckanext.fair3r.lib import mailer as fair3r_mailer
from ckanext.fair3r.lib.actions import (
    external_lookup,
    external_lookup_auth,
    xenbase_strains,
    xenbase_strains_auth,
)
from ckanext.fair3r.lib.fdf.schema import load_fdf_schema

log = logging.getLogger(__name__)

# Routing: register blueprints (`IBlueprint`) to expose custom endpoints.
# Templating/theming: add template/public asset paths (`IConfigurer`) for overrides.
# Authz/action overrides: expose `get_auth_functions` (`IAuthFunctions`) or `get_actions`.
# CLI/admin hooks: (removed - tasks now run via cron/Ansible)
# Validation and schema: implement `IDatasetForm` or `IValidators`.

log = getLogger(__name__)


class Fair3RPlugin(plugins.SingletonPlugin, DefaultTranslation):
    plugins.implements(plugins.ITranslation)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(IDoi, inherit=True)
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IFacets)

    # IConfigurer

    def update_config(self, config_):
        here = os.path.dirname(__file__)
        toolkit.add_template_directory(config_, os.path.join(here, "templates"))
        toolkit.add_public_directory(config_, os.path.join(here, "public"))
        toolkit.add_template_directory(
            config_, os.path.join(here, "templates", "snippets")
        )
        toolkit.add_resource("assets", "fair3r")

        # Override CKAN mailer functions with our custom ones
        self._override_mailer_functions()

    def get_helpers(self):
        return {
            "fair3r_current_user": self.fair3r_current_user,
            "fair3r_is_authenticated": self.fair3r_is_authenticated,
            "fair3r_is_resource_read": self.fair3r_is_resource_read,
            "fair3r_context": self.fair3r_context,
            "fair3r_is_superadmin": self.fair3r_is_superadmin,
            "fdf_schema": self._get_fdf_schema,
            "parse_fdf_json": self.parse_fdf_json,
            "fdf_schema_sections": self._get_fdf_schema_sections,
            "extract_fdf_section_data": self.extract_fdf_section_data,
            "fdf_split_symbol_sup": self.fdf_split_symbol_sup,
            "fair3r_license_options": self.fair3r_license_options,
            "fair3r_member_count_label": self.fair3r_member_count_label,
        }

    # Gene/allele nomenclature from external databases (MGI, Alliance
    # Genome...) writes the allele designation as an HTML superscript,
    # e.g. "Apoe<sup>Tg(rtTA)1Gaga</sup>". These same FDF fields also accept
    # manual free-text entry, so raw HTML from here is never trusted or
    # marked safe. Instead of allow-listing tags, we only recognize this one
    # specific, known shape and split it into two plain-text pieces; the
    # template wraps them with its own literal <sup> tag and renders both
    # through Jinja's normal auto-escaping, same as any other subject text.
    # Anything that doesn't match this exact pattern (including any other
    # markup) is returned as plain text and shown as-is, autoescaped.
    _SYMBOL_SUP_RE = re.compile(r"^(.*?)<sup>(.*?)</sup>$", re.IGNORECASE | re.DOTALL)

    @classmethod
    def fdf_split_symbol_sup(cls, text):
        """Split a gene/allele symbol into its base and superscript parts
        for template-side rendering. Returns {"base": ..., "sup": ...};
        "sup" is empty when `text` doesn't match the "X<sup>Y</sup>" shape,
        in which case "base" is just the original text, untouched."""
        if text is None:
            return {"base": "", "sup": ""}
        raw = str(text)
        match = cls._SYMBOL_SUP_RE.match(raw)
        if match:
            return {"base": match.group(1), "sup": match.group(2)}
        return {"base": raw, "sup": ""}

    # Mapping of CKAN license IDs to their short acronyms.
    _LICENSE_ACRONYMS: ClassVar[dict[str, str]] = {
        "cc-zero": "CC0",
        "cc-by": "CC BY",
        "cc-by-sa": "CC BY-SA",
        "cc-nc": "CC NC",
        "odc-pddl": "PDDL",
        "odc-by": "ODC-By",
        "odc-odbl": "ODbL",
        "gfdl": "GFDL",
        "uk-ogl": "OGL",
    }

    @classmethod
    def fair3r_license_options(cls, existing_license_id=None):
        """Wrap h.license_options() and append the acronym to each title."""
        from ckan.lib.helpers import license_options

        options = []
        for license_id, license_desc in license_options(existing_license_id):
            acronym = cls._LICENSE_ACRONYMS.get(license_id)
            if acronym and f"({acronym})" not in license_desc:
                license_desc = f"{license_desc} ({acronym})"
            options.append((license_id, license_desc))
        return options

    def fair3r_member_count_label(self, count):
        """Member count for organization/group cards (CKAN core fr catalog gap)."""
        if count:
            return toolkit.ungettext(
                "{num} Member",
                "{num} Members",
                count,
            ).format(num=count)
        return toolkit._("0 Members")

    @staticmethod
    def _localized_license_facet_title(facets_dict):
        """License facet label (CKAN core fr catalog leaves 'Licenses' untranslated)."""
        for key in ("license_id", "license"):
            if key in facets_dict:
                facets_dict[key] = toolkit._("Licenses")
        return facets_dict

    def dataset_facets(self, facets_dict, package_type):
        return self._localized_license_facet_title(facets_dict)

    def group_facets(self, facets_dict, group_type, package_type):
        return self._localized_license_facet_title(facets_dict)

    def organization_facets(self, facets_dict, organization_type, package_type):
        return self._localized_license_facet_title(facets_dict)

    def fair3r_context(self):
        """Fetch the fair3r context from the configuration"""
        return toolkit.config.get("ckanext.fair3r.context", None)

    def fair3r_is_superadmin(self):
        """Check if the current user is a superadmin"""
        if getattr(current_user, "is_anonymous", True):
            return False
        return bool(getattr(current_user, "sysadmin", False))

    def fair3r_current_user(self):
        """Return the current user object (or anonymous user) for templates."""
        return current_user

    def fair3r_is_authenticated(self):
        """Check if the current user is authenticated."""
        return not getattr(current_user, "is_anonymous", True)

    def fair3r_is_resource_read(self):
        """Check if the current endpoint is a resource read page."""
        endpoint = request.endpoint or ""
        return endpoint.endswith(("resource.read", "_resource.read"))

    def parse_fdf_json(self, fdf_json_string):
        """
        Parse FDF JSON string and return dict. Returns empty dict on error.
        """
        if not fdf_json_string:
            return {}
        try:
            return json.loads(fdf_json_string)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            log.error("Failed to parse FDF JSON: %s", e)
            return {}

    def _get_fdf_schema(self):
        """Load the localized FAIR3R JSON schema from the extension directory."""
        return load_fdf_schema()

    def _get_fdf_schema_sections(self):
        """
        Extract FDF schema sections in order with metadata.
        Returns list of dicts with: id, title, icon, position, display_mapping
        Used by templates to dynamically adapt to schema changes.
        """
        schema = self._get_fdf_schema()
        sections = []

        for idx, section in enumerate(schema.get("sections", [])):
            if section.get("show_in_dataset", True) is False:
                continue
            sections.append(
                {
                    "position": idx,
                    "id": section.get("id", ""),
                    "title": section.get("title", ""),
                    "icon": section.get("icon", ""),
                    "repeatable": bool(section.get("repeatable", False)),
                    "subject_scheme": section.get("subject_scheme"),
                    "display_mapping": section.get("display_mapping", {}),
                }
            )

        return sections

    def get_commands(self):
        return cli.get_commands()

    def extract_fdf_section_data(self, fdf_data, section):
        """
        Extract data from FDF output based on section's display_mapping.
        Returns structured data ready for template display.

        Supports:
        - Direct field access: {"source": "experimentalInterventions"}
        - Filtered subjects: {"source": "subjects", "filter": {"subjectScheme": "NCBITaxon"}}
        - Complex fields: {"source": "titles", "publicationYear", "types"}
        """
        if not isinstance(fdf_data, dict) or not isinstance(section, dict):
            return None

        section_id = (
            section.get("id", "<unknown>") if isinstance(section, dict) else "<unknown>"
        )

        mapping = section.get("display_mapping", {})
        if not isinstance(mapping, dict) or not mapping:
            log.warning(
                "FDF display mapping missing or invalid for section '%s'",
                section_id,
            )
            return None

        source = mapping.get("source")
        if source in (None, ""):
            log.warning(
                "FDF display mapping source missing for section '%s'",
                section_id,
            )
            return None

        def _has_display_value(value):
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, list):
                return any(_has_display_value(v) for v in value)
            if isinstance(value, dict):
                return any(_has_display_value(v) for v in value.values())
            return True

        def _clean_for_display(value):
            if isinstance(value, str):
                cleaned = value.strip()
                return cleaned or None

            if isinstance(value, list):
                cleaned_list = []
                for item in value:
                    cleaned_item = _clean_for_display(item)
                    if _has_display_value(cleaned_item):
                        cleaned_list.append(cleaned_item)
                return cleaned_list or None

            if isinstance(value, dict):
                cleaned_dict = {}
                for k, v in value.items():
                    cleaned_v = _clean_for_display(v)
                    if _has_display_value(cleaned_v):
                        cleaned_dict[k] = cleaned_v
                return cleaned_dict or None

            return value

        def _subject_matches_filter(subj, filter_criteria):
            for key, expected in filter_criteria.items():
                subj_val = subj.get(key)
                # A subject emitted as a cross-reference of another one
                # (see _emitXrefSubjects in fdf-form.js) carries its own
                # provider as subjectScheme (e.g. "MGI") plus a
                # `crossRefOf` naming the *primary* subjectScheme it is
                # attached to (e.g. "geneAccessionId"). A section's
                # display_mapping.filter only enumerates primary schemes,
                # so fall back to crossRefOf when matching on subjectScheme
                # — this is what lets a section pick up cross-references
                # for the identifiers it already shows, without needing to
                # list every possible external provider ahead of time.
                if key == "subjectScheme" and subj.get("crossRefOf"):
                    subj_val = subj.get("crossRefOf")
                if isinstance(expected, list):
                    if subj_val not in expected:
                        return False
                elif isinstance(expected, str) and expected.startswith("^"):
                    if not subj_val or not re.match(expected, str(subj_val)):
                        return False
                else:
                    if subj_val != expected:
                        return False
            return True

        def _apply_generic_filter(items, filter_criteria, src_name):
            if not isinstance(items, list):
                return items
            if not isinstance(filter_criteria, dict) or not filter_criteria:
                filter_criteria = {}

            filtered = []
            for item in items:
                if not isinstance(item, dict):
                    continue

                # Related resources: ignore placeholder/empty rows so dataset
                # display does not show blank cards when nothing was entered.
                if src_name == "relatedIdentifiers":
                    related_identifier = str(
                        item.get("relatedIdentifier") or ""
                    ).strip()
                    if not related_identifier:
                        continue

                if src_name == "contributors":
                    contributor_name = str(item.get("name") or "").strip()
                    contributor_given = str(item.get("givenName") or "").strip()
                    contributor_family = str(item.get("familyName") or "").strip()
                    if not (
                        contributor_name or contributor_given or contributor_family
                    ):
                        continue

                if _subject_matches_filter(item, filter_criteria):
                    filtered.append(item)
            return filtered

        # Handle subjects with filtering
        if source == "subjects":
            filter_criteria = mapping.get("filter", {})
            subjects = fdf_data.get("subjects", [])

            if not isinstance(subjects, list):
                return None

            # Backward/forward-compatible: ignore malformed filter blocks.
            if not isinstance(filter_criteria, dict):
                log.warning(
                    "FDF display mapping filter is not a dict for section '%s'; ignoring filter",
                    section_id,
                )
                filter_criteria = {}

            if not filter_criteria:
                return subjects

            # Filter subjects by criteria
            filtered = [
                subj
                for subj in subjects
                if isinstance(subj, dict)
                and _subject_matches_filter(subj, filter_criteria)
            ]

            return _clean_for_display(filtered)

        # Handle multiple sources (for complex sections like title)
        if isinstance(source, list):
            result = {}
            filter_criteria = mapping.get("filter", {})
            if not isinstance(filter_criteria, dict):
                filter_criteria = {}

            for src in source:
                if not isinstance(src, str) or not src:
                    continue

                if src == "subjects":
                    subjects = fdf_data.get("subjects", [])
                    if not isinstance(subjects, list):
                        continue

                    if not filter_criteria:
                        value = subjects
                    else:
                        value = [
                            subj
                            for subj in subjects
                            if isinstance(subj, dict)
                            and _subject_matches_filter(subj, filter_criteria)
                        ]
                else:
                    value = fdf_data.get(src)

                if isinstance(value, list) and src == "subjects":
                    value = _apply_generic_filter(value, filter_criteria, src)

                if value:
                    result[src] = value
            return _clean_for_display(result)

        # Resilient fallback: avoid raising on unexpected source type.
        if not isinstance(source, str):
            log.warning(
                "FDF display mapping source has unsupported type for section '%s': %s",
                section_id,
                type(source).__name__,
            )
            return None

        # Handle simple direct access
        value = fdf_data.get(source)
        filter_criteria = mapping.get("filter", {})
        if isinstance(value, list):
            value = _apply_generic_filter(value, filter_criteria, source)
            return _clean_for_display(value)
        return _clean_for_display(value)

    def _override_mailer_functions(self):
        """
        Override CKAN mailer functions with our custom ones to support HTML emails.
        """
        ckan_mailer.send_reset_link = fair3r_mailer.send_reset_link
        ckan_mailer.send_invite = fair3r_mailer.send_invite

    # IBlueprint

    def get_blueprint(self):
        """Register extension blueprints (download-all, guards, account request, dataset creation, FDF, sitemap)."""
        return [
            download_all,
            activity_guard,
            account_request,
            dataset_choice,
            fdf,
            sitemap,
            standard_creation,
        ]

    # IActions

    def get_actions(self):
        """Expose custom server-side actions at /api/3/action/<name>."""
        return {
            "external_lookup": external_lookup,
            "xenbase_strains": xenbase_strains,
        }

    # IAuthFunctions

    def get_auth_functions(self):
        """Register auth functions for custom actions."""
        return {
            "external_lookup": external_lookup_auth,
            "xenbase_strains": xenbase_strains_auth,
        }

    # IDoi - DataCite metadata customization

    @staticmethod
    def _s(value):
        """Strip a string or return None if empty/non-string."""
        return value.strip() or None if isinstance(value, str) else value

    def _normalize_datacite_person(self, entry, default_contributor_type=None):
        """
        Convert DataCite-style person/org dict to ckanext-doi xml_utils.create_contributor format.
        Strictly filters out empty/whitespace values to prevent DataCite XML validation errors.
        """
        if not isinstance(entry, dict):
            return None

        is_org = (entry.get("nameType") or "").lower() == "organizational" or bool(
            entry.get("is_org")
        )
        full_name = self._s(entry.get("name") or entry.get("full_name"))
        family_name = self._s(entry.get("familyName") or entry.get("family_name"))
        given_name = self._s(entry.get("givenName") or entry.get("given_name"))

        if not full_name:
            full_name = (
                f"{family_name}, {given_name}"
                if family_name and given_name
                else family_name or given_name
            )
        if not full_name:
            return None

        normalized = {"full_name": full_name, "is_org": is_org}
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

        # Prefer pre-structured affiliation_objects (set by datacite_converter) which
        # carry affiliationIdentifier/affiliationIdentifierScheme; fall back to raw
        # affiliations/affiliation which may be strings or dicts from the FDF form.
        raw_aff_objects = entry.get("affiliation_objects")
        affiliations = (
            entry.get("affiliations")
            if entry.get("affiliations") is not None
            else entry.get("affiliation")
        )
        if raw_aff_objects is not None:
            # Already normalized — pass through directly.
            if not isinstance(raw_aff_objects, list):
                raw_aff_objects = [raw_aff_objects]
            aff_values = []
            aff_objects = []
            for a in raw_aff_objects:
                if isinstance(a, dict):
                    name = str(a.get("affiliation", "") or a.get("name", "")).strip()
                    aff_id = self._s(
                        a.get("affiliationIdentifier")
                        or a.get("affiliation_identifier")
                    )
                    aff_scheme = self._s(
                        a.get("affiliationIdentifierScheme")
                        or a.get("affiliation_scheme")
                    )
                    aff_scheme_uri = self._s(
                        a.get("schemeURI") or a.get("schemeUri") or a.get("scheme_uri")
                    )
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
            if aff_values:
                normalized["affiliations"] = aff_values
            if aff_objects:
                normalized["affiliation_objects"] = aff_objects
        elif affiliations is not None:
            if not isinstance(affiliations, list):
                affiliations = [affiliations]
            aff_values = []
            aff_objects = []  # full dicts preserving affiliationIdentifier etc.
            for a in affiliations:
                if isinstance(a, dict):
                    name = str(a.get("affiliation", "") or a.get("name", "")).strip()
                    if name:
                        aff_values.append(name)
                    aff_id = self._s(
                        a.get("affiliationIdentifier")
                        or a.get("affiliation_identifier")
                    )
                    aff_scheme = self._s(
                        a.get("affiliationIdentifierScheme")
                        or a.get("affiliation_scheme")
                    )
                    aff_scheme_uri = self._s(a.get("schemeURI") or a.get("scheme_uri"))
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
                id_val = self._s(idf.get("identifier") or idf.get("nameIdentifier"))
                scheme = self._s(idf.get("scheme") or idf.get("nameIdentifierScheme"))
                scheme_uri = self._s(idf.get("scheme_uri") or idf.get("schemeURI"))
                if id_val and scheme:
                    entry_dict = {"identifier": id_val, "scheme": scheme}
                    if scheme_uri:
                        entry_dict["scheme_uri"] = scheme_uri
                    id_values.append(entry_dict)
            if id_values:
                normalized["identifiers"] = id_values

        return normalized

    def _dedupe_people(self, people, include_contributor_type=False):
        """Remove duplicate normalized people entries while preserving order."""
        unique_people = []
        seen = set()

        for person in people or []:
            if not isinstance(person, dict):
                continue

            key = (
                (person.get("full_name") or "").strip().lower(),
                (person.get("family_name") or "").strip().lower(),
                (person.get("given_name") or "").strip().lower(),
                bool(person.get("is_org")),
                tuple(sorted(person.get("affiliations", []) or [])),
                tuple(
                    sorted(
                        (
                            (identifier.get("identifier") or "").strip().lower(),
                            (identifier.get("scheme") or "").strip().lower(),
                            (identifier.get("scheme_uri") or "").strip().lower(),
                        )
                        for identifier in (person.get("identifiers") or [])
                        if isinstance(identifier, dict)
                    )
                ),
            )

            if include_contributor_type:
                key = key + (((person.get("contributor_type") or "").strip().lower(),),)

            if key in seen:
                continue

            seen.add(key)
            unique_people.append(person)

        return unique_people

    def _drop_researcher_when_specific_contributor_exists(self, people):
        """For the same person, drop generic Researcher contributors when a more specific contributor type exists."""
        if not isinstance(people, list):
            return []

        grouped = {}
        for idx, person in enumerate(people):
            if not isinstance(person, dict):
                continue
            identity_key = (
                (person.get("full_name") or "").strip().lower(),
                (person.get("family_name") or "").strip().lower(),
                (person.get("given_name") or "").strip().lower(),
                bool(person.get("is_org")),
            )
            grouped.setdefault(identity_key, []).append((idx, person))

        drop_indexes = set()
        for entries in grouped.values():
            has_specific_type = any(
                (
                    (p.get("contributor_type") or "").strip().lower()
                    not in ("", "researcher")
                )
                for _, p in entries
            )
            if not has_specific_type:
                continue
            for idx, person in entries:
                if (
                    person.get("contributor_type") or ""
                ).strip().lower() == "researcher":
                    drop_indexes.add(idx)

        return [p for idx, p in enumerate(people) if idx not in drop_indexes]

    def _metadata_person_to_xml_person(self, person, include_contributor_type=False):
        """Convert normalized metadata_dict person payload to xml_dict person payload."""
        if not isinstance(person, dict):
            return None

        full_name = self._s(person.get("full_name") or person.get("name"))
        family_name = self._s(person.get("family_name") or person.get("familyName"))
        given_name = self._s(person.get("given_name") or person.get("givenName"))
        is_org = bool(person.get("is_org"))

        if not full_name:
            full_name = (
                f"{family_name}, {given_name}"
                if family_name and given_name
                else family_name or given_name
            )
        if not full_name:
            return None

        xml_person = {
            "name": full_name,
            "nameType": "Organizational" if is_org else "Personal",
        }
        if family_name:
            xml_person["familyName"] = family_name
        if given_name:
            xml_person["givenName"] = given_name

        if include_contributor_type:
            contributor_type = self._s(
                person.get("contributor_type") or person.get("contributorType")
            )
            if contributor_type:
                xml_person["contributorType"] = contributor_type

        identifiers = person.get("identifiers") or person.get("nameIdentifiers") or []
        if not isinstance(identifiers, list):
            identifiers = [identifiers]
        xml_identifiers = []
        for identifier in identifiers:
            if not isinstance(identifier, dict):
                continue
            identifier_value = self._s(
                identifier.get("identifier") or identifier.get("nameIdentifier")
            )
            identifier_scheme = self._s(
                identifier.get("scheme") or identifier.get("nameIdentifierScheme")
            )
            scheme_uri = self._s(
                identifier.get("scheme_uri") or identifier.get("schemeURI")
            )
            if not (identifier_value and identifier_scheme):
                continue
            xml_identifier = {
                "nameIdentifier": identifier_value,
                "nameIdentifierScheme": identifier_scheme,
            }
            if scheme_uri:
                xml_identifier["schemeURI"] = scheme_uri
            xml_identifiers.append(xml_identifier)
        if xml_identifiers:
            xml_person["nameIdentifiers"] = xml_identifiers

        affiliations = (
            person.get("affiliation_objects")
            or person.get("affiliation")
            or person.get("affiliations")
            or []
        )
        if not isinstance(affiliations, list):
            affiliations = [affiliations]
        xml_affiliations = []
        for affiliation in affiliations:
            if isinstance(affiliation, dict):
                affiliation_name = self._s(
                    affiliation.get("affiliation") or affiliation.get("name")
                )
                affiliation_id = self._s(
                    affiliation.get("affiliationIdentifier")
                    or affiliation.get("affiliation_identifier")
                )
                affiliation_scheme = self._s(
                    affiliation.get("affiliationIdentifierScheme")
                    or affiliation.get("affiliation_scheme")
                )
                scheme_uri = self._s(
                    affiliation.get("schemeURI")
                    or affiliation.get("schemeUri")
                    or affiliation.get("scheme_uri")
                )
                if not affiliation_name:
                    continue
                # DataCite JSON expects affiliation items to use 'name' for the label
                xml_affiliation = {"name": affiliation_name}
                if affiliation_id:
                    xml_affiliation["affiliationIdentifier"] = affiliation_id
                if affiliation_scheme:
                    xml_affiliation["affiliationIdentifierScheme"] = affiliation_scheme
                if scheme_uri:
                    xml_affiliation["schemeURI"] = scheme_uri
                xml_affiliations.append(xml_affiliation)
            else:
                affiliation_name = self._s(affiliation)
                if affiliation_name:
                    xml_affiliations.append({"name": affiliation_name})
        if xml_affiliations:
            xml_person["affiliation"] = xml_affiliations

        return xml_person

    def build_metadata_dict(self, pkg_dict, metadata_dict, errors):
        """
        Override default DataCite metadata generation to use our structured datacite.* extras
        instead of letting ckanext-doi use generic field extraction.

        :param pkg_dict: CKAN package dictionary
        :param metadata_dict: metadata dict being built by ckanext-doi
        :param errors: errors dict tracking failed extractions
        :returns: (metadata_dict, errors)
        """
        extras = pkg_dict.get("extras", [])
        datacite_extras = {}

        # Extract all datacite.* extras.
        # Values may be JSON (lists/dicts) or plain strings (e.g. publisherIdentifier).
        for extra in extras:
            key = extra.get("key", "")
            if key.startswith("datacite."):
                field_name = key.replace(
                    "datacite.", ""
                )  # e.g., 'creators', 'subjects'
                raw_value = extra.get("value", "")
                if raw_value is None:
                    continue
                if not isinstance(raw_value, str):
                    datacite_extras[field_name] = raw_value
                    continue

                raw_value = raw_value.strip()
                if not raw_value:
                    continue

                try:
                    datacite_extras[field_name] = json.loads(raw_value)
                except (json.JSONDecodeError, TypeError):
                    # Keep non-JSON scalar values as plain strings.
                    datacite_extras[field_name] = raw_value

        # Prefer FAIR3R datacite creators when available because they can carry
        # richer identifiers/affiliations (ORCID, ROR) than base author extraction.
        if datacite_extras.get("creators"):
            normalized_creators = self._dedupe_people(
                [
                    n
                    for c in datacite_extras["creators"]
                    for n in [self._normalize_datacite_person(c)]
                    if n
                ]
            )
            if normalized_creators:
                metadata_dict["creators"] = normalized_creators
                errors.pop("creators", None)

        if datacite_extras.get("titles"):
            metadata_dict["titles"] = datacite_extras["titles"]
            errors.pop("titles", None)

        if datacite_extras.get("subjects"):
            metadata_dict["subjects"] = datacite_extras["subjects"]
            errors.pop("subjects", None)

        if datacite_extras.get("descriptions"):
            merged_descriptions = []
            seen_description_keys = set()

            def _add_description_items(items):
                if not isinstance(items, list):
                    return
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    description_value = (item.get("description") or "").strip()
                    if not description_value:
                        continue
                    description_type = (item.get("descriptionType") or "Other").strip()
                    dedupe_key = (description_type.lower(), description_value.lower())
                    if dedupe_key in seen_description_keys:
                        continue
                    seen_description_keys.add(dedupe_key)
                    merged_descriptions.append(
                        {
                            "description": description_value,
                            "descriptionType": description_type,
                        }
                    )

            # Prefer CKAN dataset notes as human Abstract when available.
            notes_text = (pkg_dict.get("notes") or "").strip()
            if notes_text:
                _add_description_items(
                    [
                        {
                            "description": notes_text,
                            "descriptionType": "Abstract",
                        }
                    ]
                )

            # Keep FAIR3R/DataCite descriptions and preserve generic extras from base ckanext-doi.
            _add_description_items(datacite_extras.get("descriptions"))
            _add_description_items(metadata_dict.get("descriptions"))

            description_type_priority = {
                "abstract": 0,
                "methods": 1,
                "technicalinfo": 2,
                "other": 3,
            }

            merged_descriptions.sort(
                key=lambda item: (
                    description_type_priority.get(
                        (item.get("descriptionType") or "").strip().lower(),
                        99,
                    ),
                    (item.get("description") or "").strip().lower(),
                )
            )

            # Keep concise but informative descriptions: Abstract first, then Methods when available.
            if merged_descriptions:
                selected_descriptions = []

                first_abstract = next(
                    (
                        d
                        for d in merged_descriptions
                        if (d.get("descriptionType") or "").strip().lower()
                        == "abstract"
                    ),
                    None,
                )
                if first_abstract:
                    selected_descriptions.append(first_abstract)

                first_methods = next(
                    (
                        d
                        for d in merged_descriptions
                        if (d.get("descriptionType") or "").strip().lower() == "methods"
                    ),
                    None,
                )
                if first_methods:
                    selected_descriptions.append(first_methods)

                merged_descriptions = selected_descriptions or merged_descriptions[:1]

            if merged_descriptions:
                metadata_dict["descriptions"] = merged_descriptions
                errors.pop("descriptions", None)

        existing_contributors = metadata_dict.get("contributors") or []
        if datacite_extras.get("contributors"):
            normalized_existing_contributors = [
                n
                for c in existing_contributors
                for n in [self._normalize_datacite_person(c)]
                if n
            ]
            normalized_fair3r_contributors = [
                n
                for c in datacite_extras["contributors"]
                for n in [
                    self._normalize_datacite_person(
                        c, default_contributor_type="Researcher"
                    )
                ]
                if n
            ]

            all_contribs = (
                normalized_existing_contributors + normalized_fair3r_contributors
            )

            # Dedupe by canonical identity (family/given/is_org) to catch differently
            # formatted names that would otherwise be treated as distinct contributors (e.g. "Smith, John" vs "John Smith").
            def _identity_key(p):
                """Return a canonical identity key (family, given, is_org) for a person dict.

                Attempts to derive family/given from explicit fields or by parsing full_name
                (handles 'Family, Given' and 'Given Family' formats).
                """
                if not isinstance(p, dict):
                    return ("", "", False)

                is_org = bool(p.get("is_org"))

                fam = (p.get("family_name") or "").strip()
                giv = (p.get("given_name") or "").strip()

                if not fam and not giv:
                    full = (p.get("full_name") or "").strip()
                    if "," in full:
                        parts = [s.strip() for s in full.split(",", 1)]
                        fam = parts[0]
                        giv = parts[1] if len(parts) > 1 else ""
                    else:
                        # attempt split on last space
                        parts = full.rsplit(" ", 1)
                        if len(parts) == 2:
                            giv, fam = parts[0].strip(), parts[1].strip()
                        else:
                            fam = full

                return (fam.lower(), giv.lower(), is_org)

            def _dedupe_by_canonical(people):
                deduped = []
                index = {}

                def _merge_into(existing, person):
                    for k in ("family_name", "given_name"):
                        if not existing.get(k) and person.get(k):
                            existing[k] = person[k]
                    # merge affiliations
                    existing_affs = set(existing.get("affiliations") or [])
                    new_affs = set(person.get("affiliations") or [])
                    merged_affs = list(existing_affs.union(new_affs))
                    if merged_affs:
                        existing["affiliations"] = merged_affs

                    # merge affiliation_objects
                    def _aff_key(a):
                        return (
                            (a.get("name") or "").strip().lower(),
                            (a.get("affiliationIdentifier") or "").strip().lower(),
                            (a.get("affiliationIdentifierScheme") or "")
                            .strip()
                            .lower(),
                        )

                    existing_objs = existing.get("affiliation_objects") or []
                    new_objs = person.get("affiliation_objects") or []
                    seen_objs = {
                        _aff_key(a): a for a in existing_objs if isinstance(a, dict)
                    }
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
                    def _id_key(i):
                        return (
                            (i.get("identifier") or "").strip().lower(),
                            (i.get("scheme") or "").strip().lower(),
                            (i.get("scheme_uri") or "").strip().lower(),
                        )

                    existing_ids = {
                        _id_key(i): i
                        for i in existing.get("identifiers") or []
                        if isinstance(i, dict)
                    }
                    for i in person.get("identifiers") or []:
                        if not isinstance(i, dict):
                            continue
                        ik = _id_key(i)
                        if ik not in existing_ids:
                            existing.setdefault("identifiers", []).append(i)
                            existing_ids[ik] = i

                for person in people or []:
                    if not isinstance(person, dict):
                        continue
                    key = _identity_key(person)
                    if key in index:
                        _merge_into(deduped[index[key]], person)
                    else:
                        # copy to avoid mutating source
                        copy = dict(person)
                        index[key] = len(deduped)
                        deduped.append(copy)
                return deduped

            merged_contributors = _dedupe_by_canonical(all_contribs)

            # Build contributor_type preferences per identity: prefer any non-'researcher' type
            type_map = {}
            for p in all_contribs:
                if not isinstance(p, dict):
                    continue
                key = _identity_key(p)
                ct = (p.get("contributor_type") or "").strip()
                if not ct:
                    continue
                existing = type_map.get(key)
                if not existing:
                    type_map[key] = ct
                else:
                    # prefer non-researcher over researcher
                    if (
                        existing.strip().lower() == "researcher"
                        and ct.strip().lower() != "researcher"
                    ):
                        type_map[key] = ct

            for person in merged_contributors:
                key = _identity_key(person)
                if key in type_map:
                    person["contributor_type"] = type_map[key]

            # Ensure family/given name fields are populated when possible and
            # normalize full_name to 'family, given' when we have both parts.
            for person in merged_contributors:
                if not isinstance(person, dict):
                    continue
                fam = (person.get("family_name") or "").strip()
                giv = (person.get("given_name") or "").strip()
                full = (person.get("full_name") or "").strip()
                # If missing family/given, try to parse from full_name
                if not fam and not giv and full:
                    if "," in full:
                        parts = [s.strip() for s in full.split(",", 1)]
                        fam = parts[0]
                        giv = parts[1] if len(parts) > 1 else ""
                    else:
                        parts = full.rsplit(" ", 1)
                        if len(parts) == 2:
                            giv, fam = parts[0].strip(), parts[1].strip()
                        else:
                            fam = full
                # apply back if parsed
                if fam and not person.get("family_name"):
                    person["family_name"] = fam
                if giv and not person.get("given_name"):
                    person["given_name"] = giv
                # Normalize full_name to 'family, given' when both parts are known
                if fam and giv:
                    person["full_name"] = f"{fam}, {giv}"

            merged_contributors = (
                self._drop_researcher_when_specific_contributor_exists(
                    merged_contributors
                )
            )
            if merged_contributors:
                metadata_dict["contributors"] = merged_contributors
                errors.pop("contributors", None)

        if "publicationYear" in datacite_extras:
            metadata_dict["publicationYear"] = datacite_extras["publicationYear"]
            errors.pop("publicationYear", None)

        if datacite_extras.get("types") and "resourceType" in datacite_extras["types"]:
            metadata_dict["resourceType"] = datacite_extras["types"]["resourceType"]
            errors.pop("resourceType", None)

        if datacite_extras.get("publisherIdentifier"):
            metadata_dict["publisherIdentifier"] = datacite_extras[
                "publisherIdentifier"
            ]
            errors.pop("publisherIdentifier", None)

        if datacite_extras.get("publisherIdentifierScheme"):
            metadata_dict["publisherIdentifierScheme"] = datacite_extras[
                "publisherIdentifierScheme"
            ]
            errors.pop("publisherIdentifierScheme", None)

        if datacite_extras.get("schemeURI"):
            metadata_dict["schemeURI"] = datacite_extras["schemeURI"]
            errors.pop("schemeURI", None)

        if datacite_extras.get("relatedIdentifiers"):
            metadata_dict["relatedIdentifiers"] = datacite_extras["relatedIdentifiers"]
            errors.pop("relatedIdentifiers", None)
            log.info(
                "Fair3R IDoi: Added %d relatedIdentifiers from datacite extras",
                len(datacite_extras["relatedIdentifiers"]),
            )
        else:
            log.info("Fair3R IDoi: No relatedIdentifiers found in datacite extras")

        return metadata_dict, errors

    def build_xml_dict(self, metadata_dict, xml_dict):
        """
        Optional customization of the final XML dict structure.
        Currently just passes through since build_metadata_dict handles everything.

        :param metadata_dict: metadata dict from build_metadata_dict
        :param xml_dict: XML-ready dict for datacite.schema42.tostring()
        :returns: xml_dict
        """

        # ckanext-doi may not always carry custom keys from metadata_dict into xml_dict.
        # Ensure FAIR3R related identifiers survive up to XML serialization.
        metadata_related_identifiers = metadata_dict.get("relatedIdentifiers") or []
        xml_related_identifiers = xml_dict.get("relatedIdentifiers") or []
        if metadata_related_identifiers and not xml_related_identifiers:
            xml_dict["relatedIdentifiers"] = metadata_related_identifiers
            log.info(
                "Fair3R IDoi: Injected %d relatedIdentifiers into xml_dict from metadata_dict",
                len(metadata_related_identifiers),
            )
        else:
            log.info(
                "Fair3R IDoi: relatedIdentifiers pre-xml status metadata=%d xml=%d",
                len(metadata_related_identifiers),
                len(xml_related_identifiers),
            )

        # ckanext-doi may also keep only its own auto-generated contributors in xml_dict.
        # Use the merged FAIR3R contributor payload from metadata_dict as the source of truth.
        metadata_contributors = metadata_dict.get("contributors") or []
        xml_contributors = xml_dict.get("contributors") or []
        if metadata_contributors:
            normalized_xml_contributors = [
                xml_person
                for contributor in metadata_contributors
                for xml_person in [
                    self._metadata_person_to_xml_person(
                        contributor, include_contributor_type=True
                    )
                ]
                if xml_person
            ]
            xml_dict["contributors"] = normalized_xml_contributors
            log.info(
                "Fair3R IDoi: Injected %d contributors into xml_dict from metadata_dict (previous xml count=%d)",
                len(normalized_xml_contributors),
                len(xml_contributors),
            )
        else:
            log.info(
                "Fair3R IDoi: contributors pre-xml status metadata=%d xml=%d",
                len(metadata_contributors),
                len(xml_contributors),
            )

        def _clean_xml_value(value):
            if isinstance(value, str):
                cleaned = value.strip()
                return cleaned if cleaned else None

            if isinstance(value, list):
                cleaned_list = []
                for item in value:
                    cleaned_item = _clean_xml_value(item)
                    if cleaned_item is not None:
                        cleaned_list.append(cleaned_item)
                return cleaned_list if cleaned_list else None

            if isinstance(value, dict):
                cleaned_dict = {}
                for key, item in value.items():
                    cleaned_item = _clean_xml_value(item)
                    if cleaned_item is not None:
                        cleaned_dict[key] = cleaned_item
                return cleaned_dict if cleaned_dict else None

            return value

        # Ensure rights entries include non-empty text content.
        # DataCite rejects empty <rights/> elements with minLength validation errors.
        rights_list = xml_dict.get("rightsList") or []
        sanitized_rights_list = []
        for right in rights_list:
            if not isinstance(right, dict):
                continue
            right_copy = dict(right)
            rights_text = right_copy.get("rights")
            if isinstance(rights_text, str):
                rights_text = rights_text.strip()
            if not rights_text:
                rights_text = (
                    right_copy.get("rightsIdentifier")
                    or right_copy.get("rightsURI")
                    or toolkit._("License information")
                )
            right_copy["rights"] = str(rights_text)
            sanitized_rights_list.append(right_copy)
        if sanitized_rights_list:
            xml_dict["rightsList"] = sanitized_rights_list
        elif "rightsList" in xml_dict:
            xml_dict.pop("rightsList", None)

        # Remove invalid date entries (eg date=None) that can produce invalid XML values.
        sanitized_dates = []
        for d in xml_dict.get("dates") or []:
            if not isinstance(d, dict):
                continue
            date_text = str(d.get("date") or "").strip()
            if date_text and date_text.lower() != "none":
                sanitized_dates.append({**d, "date": date_text})
        if sanitized_dates:
            xml_dict["dates"] = sanitized_dates
        else:
            xml_dict.pop("dates", None)

        # Remove only the auto-generated placeholder relatedIdentifier pointing to
        # DataCite API endpoint when it is marked as IsDerivedFrom.
        sanitized_related_identifiers = []
        for identifier in xml_dict.get("relatedIdentifiers") or []:
            if not isinstance(identifier, dict):
                continue
            rid = str(identifier.get("relatedIdentifier") or "").strip()
            if not rid:
                continue
            relation_type = str(identifier.get("relationType") or "").strip().lower()
            if (
                rid.lower().startswith("https://api.test.datacite.org/dois")
                and relation_type == "isderivedfrom"
            ):
                continue
            sanitized_related_identifiers.append(identifier)

        if sanitized_related_identifiers:
            xml_dict["relatedIdentifiers"] = sanitized_related_identifiers
        else:
            xml_dict.pop("relatedIdentifiers", None)

        # Final deep cleanup to remove any empty nested values generated by upstream helpers.
        keys_to_clean = [
            "creators",
            "titles",
            "subjects",
            "contributors",
            "dates",
            "rightsList",
            "descriptions",
            "formats",
            "sizes",
            "types",
            "publisher",
            "language",
            "publicationYear",
        ]
        for key in keys_to_clean:
            if key not in xml_dict:
                continue
            cleaned_value = _clean_xml_value(xml_dict.get(key))
            if cleaned_value is None:
                xml_dict.pop(key, None)
            else:
                xml_dict[key] = cleaned_value

        # Ensure contributors with empty personal-name parts don't leak empty tags.
        sanitized_contributors = []
        for c in xml_dict.get("contributors") or []:
            if (
                isinstance(c, dict)
                and isinstance(c.get("name"), str)
                and c["name"].strip()
            ):
                copy = {
                    k: v
                    for k, v in c.items()
                    if k not in ("givenName", "familyName") or v
                }
                sanitized_contributors.append(copy)
        if sanitized_contributors:
            xml_dict["contributors"] = sanitized_contributors
        else:
            xml_dict.pop("contributors", None)

        return xml_dict
