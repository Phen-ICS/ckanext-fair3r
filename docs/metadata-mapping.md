# Metadata mapping

Three layers, each derived from the previous one on every FDF save:

```
fdf_output_json  --(datacite_converter.py)-->  datacite.* extras
                 --(converter.py)----------->  author / maintainer
datacite.* extras + CKAN fields --(plugin.py IDoi)--> ckanext-doi --> DataCite XML
datacite.* extras + CKAN fields --(RDF profiles)----> DCAT-AP, Croissant, schema.org
```

The `datacite.*` extras are rewritten as a whole each time (old ones
removed, new ones added), so they always reflect the current answers.
They're only produced by the FDF form: a dataset created or edited
through the API without `fdf_output_json` keeps whatever extras it was
given.

## FDF answers -> `datacite.*` extras

`DataCiteConverter.fdf_to_datacite` then `convert_fdf_to_datacite_extras`
(one extra per field, JSON value; empty values left out):

| Extra | From the answers |
|---|---|
| `datacite.creators` | `creators[]`. Person: `name` = "Family, Given" (or the one part given), `givenName`, `familyName`, ORCID `nameIdentifiers`, affiliations (ROR), CRediT `contributorRoles`. Organization (`nameType = Organizational`): `organization_name`. Entries without any name are dropped; then reshaped for ckanext-doi (`full_name`, `family_name`, `given_name`, `is_org`, `affiliations`, `identifiers`) and deduplicated. |
| `datacite.contributors` | `contributors[]`, same shape, with `contributorType` (default `Researcher`); deduplicated per person and type |
| `datacite.titles` | `titles[]` (type `AlternativeTitle` unless given; the main title is CKAN's) |
| `datacite.publicationYear` | `publicationYear` |
| `datacite.publisher`, `publisherIdentifier`, `publisherIdentifierScheme`, `schemeURI` | `publisher`, `publisherIdentifier`; the scheme is inferred from the identifier (ROR, ORCID or DOI) |
| `datacite.types` | First of `types[]`; default `Dataset` / `Dataset` |
| `datacite.subjects` | `subjects[]`: `subject`, `subjectScheme`, `valueURI` and `schemeURI` when they're valid absolute URIs (invalid ones dropped, logged). Old UI prefixes ("Gene: ", "Strain: "...) stripped from labels. Plus subjects rebuilt from older structured keys (`geneSymbol`, `alleleSymbol`, `treatmentName`...) when present. Deduplicated on label + scheme + URI. |
| `datacite.descriptions` | `descriptions[]` as given (default type `Abstract`), plus a generated **Methods** description summarizing the form: resource type, creators, contributors, then every answer under the label the schema displays it with (see below) |
| `datacite.relatedIdentifiers` | `relatedIdentifiers[]`: identifier, type (default `URL`), relation type - `IsRelatedTo` and any value outside DataCite's list become `References` |

### The Methods summary

`lib/fdf/summary.py` reads the labels from the schema, not from code, so
a new ontology or section needs no code change:

- each section's `display_mapping` says which subjects it shows
  (`filter.subjectScheme`) and which other answers (`source`); a value goes
  under `labels[scheme]` or `labels[key]`, else the section's title;
- choice answers are shown by their option label (`GENE` -> "Genetic
  Modification");
- cross-references (`crossRefOf`) are left out: they repeat their primary
  gene or allele;
- a subject no section claims (an older scheme, or no schema loaded) goes
  under its own scheme name, so nothing entered is dropped.

Example: "Species: Mus musculus", "Gene: Apoe", "Disease Model: Rett
syndrome". ckanext-zenodo uses the same lines in the Zenodo record.

## Author and maintainer

`FDFConverter.convert_to_ckan_dataset` fills CKAN's single-value contact
fields from `creators[]`:

- **maintainer**: the first creator whose role is Maintainer or
  DataManager (or who is listed as a DataManager contributor);
- **author**: the first other creator;
- name = "Given Family", email from the creator.

A field is only set when the FDF gives it a value.

## DataCite (through ckanext-doi)

ckanext-doi builds its own metadata from the dataset (title, publisher,
dates, licence, sizes, formats...), then calls this plugin:

### `build_metadata_dict`

Replaces or completes ckanext-doi's metadata with the `datacite.*`
extras, and clears the matching "missing" errors:

| Field | Rule |
|---|---|
| creators | The FDF creators when there are any (richer: ORCID, ROR), deduplicated |
| titles, subjects, publicationYear, resourceType, publisherIdentifier, publisherIdentifierScheme, schemeURI, relatedIdentifiers | Taken from the extras when present |
| descriptions | Merged and deduplicated from CKAN's description (as `Abstract`), the FDF descriptions and ckanext-doi's own; then **only the first Abstract and the first Methods** are kept |
| contributors | ckanext-doi's own plus the FDF ones, merged per person: names in any form ("Smith, John" / "John Smith") count as the same person; affiliations and identifiers are combined; a specific contributor type wins over the generic `Researcher`, and a `Researcher` duplicate of a person who has a specific type is dropped. Names normalized to "Family, Given". |

### `build_xml_dict`

Last fixes before the XML is sent to DataCite, which rejects empty
elements:

- the merged contributors and related identifiers are put into the XML
  payload (ckanext-doi may only carry its own);
- every rights entry gets a text (the licence identifier or URI, or
  "License information");
- dates without a value are removed;
- a placeholder related identifier pointing at DataCite's own test API
  (`IsDerivedFrom https://api.test.datacite.org/dois...`) is removed;
- empty strings, lists and objects are removed from every field, and
  contributors without a name, or with empty name parts, are cleaned.

## RDF profiles (ckanext-dcat)

All three read the `datacite.*` extras (`rdf_extras.py`) on top of
ckanext-dcat's own profile. The DOI is added only once DataCite has
registered it (`doi` and `doi_status` set by ckanext-doi), as
`https://doi.org/<doi>`.

| FDF | DCAT-AP (`fair3r_dcat_ap`, on EuropeanDCATAP3Profile) | schema.org / Croissant (`fair3r_schemaorg`, `fair3r_croissant`) |
|---|---|---|
| creators / contributors | `dct:creator` / `dct:contributor`: `foaf:Person` or `foaf:Organization` with `foaf:name` | `schema:creator` / `schema:contributor`: `Person` or `Organization`, `name`, `affiliation` |
| publisher | (DCAT-AP's own) | `schema:publisher` `Organization` |
| subjects | `dcat:keyword` (label); with a URI also `dct:subject` -> `skos:Concept` with `skos:prefLabel`, `skos:inScheme` a local `skos:ConceptScheme` | `schema:keywords`; with a URI also `schema:about` -> `DefinedTerm` with `name`, `inDefinedTermSet` a local `DefinedTermSet` |
| relatedIdentifiers | `dct:relation` (URI or literal) | `schema:citation` |
| DOI | `dct:identifier` | `schema:identifier` |

The local scheme for a subject's `subjectScheme` (e.g. `NCBITaxon`,
`geneAccessionId`) is `<ckan.site_url>/vocabulary/fdf-subject-scheme/<name>`,
labelled with the scheme name: FDF has no reliable registry URI per
scheme, so one is minted under the portal rather than guessed.
`fair3r_croissant` uses `https://schema.org/` (the Croissant validator
requires it), `fair3r_schemaorg` `http://schema.org/` (ckanext-dcat's own
convention). `fair3r_schemaorg` is also what `structured_data` embeds as
JSON-LD in dataset pages.
