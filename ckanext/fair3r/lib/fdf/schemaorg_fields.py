"""
Shared FAIR3R FDF -> schema.org field mapping, reused by both
CroissantProfile and the plain SchemaOrgProfile (ckanext-dcat's
"structured_data" plugin embeds the latter directly on dataset pages too,
separately from Croissant - both need the same FDF fields).

Both profiles expose the same additional_fields(dataset_ref, dataset_dict)
extension point, so this mixin can just be dropped in. The two profiles
don't agree on the schema.org namespace scheme though (Croissant requires
https://schema.org/, the plain one uses http://schema.org/ - ckanext-dcat's
own convention), so the concrete class must set a SCHEMA class attribute.
"""

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import RDF

from ckanext.fair3r.lib.fdf.rdf_extras import get_doi_url
from ckanext.fair3r.lib.fdf.rdf_extras import get_json_extra as _json_extra


class FDFSchemaOrgFieldsMixin:
    """Requires a `SCHEMA` namespace class attribute on the concrete profile."""

    def additional_fields(self, dataset_ref, dataset_dict):
        self._fdf_agents_graph(
            dataset_ref, dataset_dict, "datacite.creators", self.SCHEMA.creator
        )
        self._fdf_agents_graph(
            dataset_ref, dataset_dict, "datacite.contributors", self.SCHEMA.contributor
        )
        self._fdf_publisher_graph(dataset_ref, dataset_dict)
        self._fdf_subjects_graph(dataset_ref, dataset_dict)
        self._fdf_related_identifiers_graph(dataset_ref, dataset_dict)
        self._fdf_doi_graph(dataset_ref, dataset_dict)

    def _fdf_doi_graph(self, dataset_ref, dataset_dict):
        doi_url = get_doi_url(dataset_dict)
        if doi_url:
            self.g.add((dataset_ref, self.SCHEMA.identifier, URIRef(doi_url)))

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
                    self.SCHEMA.Organization
                    if agent.get("is_org")
                    else self.SCHEMA.Person,
                )
            )
            self.g.add((agent_ref, self.SCHEMA.name, Literal(agent["full_name"])))

            affiliations = agent.get("affiliations")
            if isinstance(affiliations, list):
                for affiliation in affiliations:
                    name = (
                        affiliation.get("name")
                        if isinstance(affiliation, dict)
                        else affiliation
                    )
                    if name:
                        self.g.add(
                            (agent_ref, self.SCHEMA.affiliation, Literal(str(name)))
                        )

    def _fdf_publisher_graph(self, dataset_ref, dataset_dict):
        publisher_name = _json_extra(dataset_dict, "datacite.publisher")
        if not publisher_name:
            return

        publisher_ref = BNode()
        self.g.add((dataset_ref, self.SCHEMA.publisher, publisher_ref))
        self.g.add((publisher_ref, RDF.type, self.SCHEMA.Organization))
        self.g.add((publisher_ref, self.SCHEMA.name, Literal(publisher_name)))

    def _fdf_subjects_graph(self, dataset_ref, dataset_dict):
        for subject in _json_extra(dataset_dict, "datacite.subjects") or []:
            if isinstance(subject, dict) and subject.get("subject"):
                self.g.add(
                    (dataset_ref, self.SCHEMA.keywords, Literal(subject["subject"]))
                )

    def _fdf_related_identifiers_graph(self, dataset_ref, dataset_dict):
        for item in _json_extra(dataset_dict, "datacite.relatedIdentifiers") or []:
            if isinstance(item, dict) and item.get("relatedIdentifier"):
                self.g.add(
                    (
                        dataset_ref,
                        self.SCHEMA.citation,
                        Literal(item["relatedIdentifier"]),
                    )
                )
