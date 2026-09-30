"""
DCAT-AP RDF profile extension exposing FAIR3R FDF metadata.

Unlike CroissantProfile, EuropeanDCATAP3Profile has no dedicated no-op
extension method to override - graph_from_dataset() does all the work
directly. So this subclass calls the parent implementation for the standard
DCAT-AP triples, then adds FDF-derived ones on the same graph, reusing the
same "datacite.*" extras as croissant_profile.py (see that module's
docstring for where they come from).
"""

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import RDF

from ckanext.dcat.profiles.base import DCAT, DCT, FOAF
from ckanext.dcat.profiles.euro_dcat_ap_3 import EuropeanDCATAP3Profile
from ckanext.fair3r.lib.fdf.rdf_extras import get_json_extra as _json_extra


def _looks_like_uri(value):
    return isinstance(value, str) and value.startswith(("http://", "https://"))


class Fair3RDCATAPProfile(EuropeanDCATAP3Profile):
    """EuropeanDCATAP3Profile extended with FAIR3R FDF form metadata."""

    def graph_from_dataset(self, dataset_dict, dataset_ref):
        super().graph_from_dataset(dataset_dict, dataset_ref)

        self._fdf_agents_graph(
            dataset_ref, dataset_dict, "datacite.creators", DCT.creator
        )
        self._fdf_agents_graph(
            dataset_ref, dataset_dict, "datacite.contributors", DCT.contributor
        )
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
                    FOAF.Organization if agent.get("is_org") else FOAF.Person,
                )
            )
            self.g.add((agent_ref, FOAF.name, Literal(agent["full_name"])))

    def _fdf_subjects_graph(self, dataset_ref, dataset_dict):
        for subject in _json_extra(dataset_dict, "datacite.subjects") or []:
            if not isinstance(subject, dict) or not subject.get("subject"):
                continue

            self.g.add((dataset_ref, DCAT.keyword, Literal(subject["subject"])))

            value_uri = subject.get("valueURI")
            if _looks_like_uri(value_uri):
                self.g.add((dataset_ref, DCT.subject, URIRef(value_uri)))

    def _fdf_related_identifiers_graph(self, dataset_ref, dataset_dict):
        for item in _json_extra(dataset_dict, "datacite.relatedIdentifiers") or []:
            if not isinstance(item, dict):
                continue

            related_identifier = item.get("relatedIdentifier")
            if not related_identifier:
                continue

            if _looks_like_uri(related_identifier):
                self.g.add((dataset_ref, DCT.relation, URIRef(related_identifier)))
            else:
                self.g.add((dataset_ref, DCT.relation, Literal(related_identifier)))
