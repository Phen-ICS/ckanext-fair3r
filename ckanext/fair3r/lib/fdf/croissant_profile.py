"""
Croissant RDF profile extension exposing FAIR3R FDF metadata.

ckanext-dcat's CroissantProfile only reads a fixed set of core CKAN dataset
fields (title, notes, license, creator, publisher, tags, temporal/spatial,
resources...). The FAIR3R Dataset Form (FDF) metadata is stored separately as
package extras (see lib/fdf/extras.py): the raw form output in
"fdf_output_json", plus a DataCite-shaped subset already flattened into
"datacite.*" extras for ckanext-doi. None of that is visible to Croissant by
default.

CroissantProfile.additional_fields() is the extension point ckanext-dcat
documents for exactly this case ("For a custom schema you should extend this
class and implement this method."). This profile reuses the same
"datacite.*" extras already produced for DOI minting, so FDF creators,
contributors, subjects and related identifiers also show up in the
Croissant/schema.org JSON-LD embedded on the dataset page.
"""

import json
import logging

from rdflib import BNode, Literal
from rdflib.namespace import RDF, Namespace

from ckanext.dcat.profiles.croissant import CroissantProfile

log = logging.getLogger(__name__)

SCHEMA = Namespace("https://schema.org/")


def _get_extra(dataset_dict, key):
    for extra in dataset_dict.get("extras", []) or []:
        if isinstance(extra, dict) and extra.get("key") == key:
            return extra.get("value")
    return None


def _json_extra(dataset_dict, key):
    raw = _get_extra(dataset_dict, key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        log.warning("Could not parse extra '%s' as JSON for Croissant output", key)
        return None


class Fair3RCroissantProfile(CroissantProfile):
    """CroissantProfile extended with FAIR3R FDF form metadata."""

    def additional_fields(self, dataset_ref, dataset_dict):
        self._fdf_agents_graph(
            dataset_ref, dataset_dict, "datacite.creators", SCHEMA.creator
        )
        self._fdf_agents_graph(
            dataset_ref, dataset_dict, "datacite.contributors", SCHEMA.contributor
        )
        self._fdf_publisher_graph(dataset_ref, dataset_dict)
        self._fdf_subjects_graph(dataset_ref, dataset_dict)
        self._fdf_related_identifiers_graph(dataset_ref, dataset_dict)

    def _fdf_agents_graph(self, dataset_ref, dataset_dict, extra_key, predicate):
        for agent in _json_extra(dataset_dict, extra_key) or []:
            if not isinstance(agent, dict) or not agent.get("full_name"):
                continue

            agent_ref = BNode()
            self.g.add((dataset_ref, predicate, agent_ref))
            self.g.add(
                (
                    agent_ref,
                    RDF.type,
                    SCHEMA.Organization if agent.get("is_org") else SCHEMA.Person,
                )
            )
            self.g.add((agent_ref, SCHEMA.name, Literal(agent["full_name"])))

            affiliations = agent.get("affiliations")
            if isinstance(affiliations, list):
                for affiliation in affiliations:
                    name = (
                        affiliation.get("name")
                        if isinstance(affiliation, dict)
                        else affiliation
                    )
                    if name:
                        self.g.add((agent_ref, SCHEMA.affiliation, Literal(str(name))))

    def _fdf_publisher_graph(self, dataset_ref, dataset_dict):
        publisher_name = _json_extra(dataset_dict, "datacite.publisher")
        if not publisher_name:
            return

        publisher_ref = BNode()
        self.g.add((dataset_ref, SCHEMA.publisher, publisher_ref))
        self.g.add((publisher_ref, RDF.type, SCHEMA.Organization))
        self.g.add((publisher_ref, SCHEMA.name, Literal(publisher_name)))

    def _fdf_subjects_graph(self, dataset_ref, dataset_dict):
        for subject in _json_extra(dataset_dict, "datacite.subjects") or []:
            if isinstance(subject, dict) and subject.get("subject"):
                self.g.add((dataset_ref, SCHEMA.keywords, Literal(subject["subject"])))

    def _fdf_related_identifiers_graph(self, dataset_ref, dataset_dict):
        for item in _json_extra(dataset_dict, "datacite.relatedIdentifiers") or []:
            if isinstance(item, dict) and item.get("relatedIdentifier"):
                self.g.add(
                    (dataset_ref, SCHEMA.citation, Literal(item["relatedIdentifier"]))
                )
