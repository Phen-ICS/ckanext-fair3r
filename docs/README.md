# ckanext-fair3r - specification

ckanext-fair3r is the CKAN plugin behind [fair3r.fr](https://fair3r.fr), a
catalogue of research datasets (animal models, phenotyping). Its core is
the **FDF** (FAIR3R Dataset Form): a metadata form generated from a JSON
schema, which looks terms up in external databases (ontologies, genes,
alleles, strains, ORCID, ROR) and stores structured, FAIR metadata on the
dataset. The plugin turns those metadata into DataCite, DCAT-AP, Croissant
and schema.org, and adds the site's theme and a few features around
datasets.

| Document | Covers |
|---|---|
| [architecture.md](architecture.md) | Components, CKAN interfaces, routes, actions, modules, templates, what's stored, dependencies on other extensions |
| [fdf-schema.md](fdf-schema.md) | The FDF schema: sections, fields, outputs, conditions, external APIs, translations, how it's loaded and updated |
| [workflows.md](workflows.md) | Every user-facing action step by step: create, add files, edit, publish, view, download, account request, activity streams |
| [metadata-mapping.md](metadata-mapping.md) | FDF answers -> `datacite.*` extras -> DataCite XML; author/maintainer; DCAT-AP, Croissant and schema.org output |
| [security.md](security.md) | Who may do what, escaping, external requests, limits, known limitations |
| [operations.md](operations.md) | Configuration reference, CLI command, deployment, troubleshooting |

## In one paragraph

A logged-in user creates a dataset with the FDF form. The browser builds
the answers as one JSON document (`fdf_output_json`); the server checks it
against the schema, stores it as a dataset extra, derives DataCite-shaped
`datacite.*` extras from it and fills CKAN's author and maintainer fields.
The dataset is saved as a **draft**, the user adds files, and "Finish"
makes it active. "Publish" makes it public: ckanext-doi then mints its DOI
with metadata built from the `datacite.*` extras (through this plugin's
`IDoi` hooks), and ckanext-zenodo publishes its Zenodo files if it has
any. The dataset page shows the FDF answers section by section, with a
completeness score; ckanext-dcat exposes the same metadata as RDF through
this plugin's profiles.

## Vocabulary

| Term | Meaning |
|---|---|
| FDF | FAIR3R Dataset Form, the metadata form this plugin adds. |
| FDF schema | `fdf_schema.json`, maintained in [fair3r-fdf-schema](https://github.com/Phen-ICS/fair3r-fdf-schema): the sections, fields, external APIs and vocabularies the form is built from. |
| FDF dataset | A dataset with an `fdf_output_json` extra, i.e. created with the FDF form. Edited with it too. |
| `fdf_output_json` | Extra holding the form's answers, a DataCite-like JSON document (`creators`, `contributors`, `subjects`, `relatedIdentifiers`...). |
| `datacite.*` extras | One extra per DataCite field (`datacite.creators`, `datacite.subjects`...), derived from `fdf_output_json` on every save; what ckanext-doi and the RDF profiles read. |
| Subject | An entry of `subjects`: a label, a `subjectScheme` (NCBITaxon, geneAccessionId, ChEBI...) and usually a `valueURI`. Organisms, strains, genes, alleles, treatments, diseases and tissues are all stored as subjects. |
| Section | A block of the form (Creators, Genes, Diet...). Some are repeatable, some appear only under a condition. |
| Completeness | A 0-100 score of how much of the applicable form is filled, in three bands (red < 50, orange, green >= 80). |
| Context | `ckanext.fair3r.context`: DEV, INTEGRATION, VALIDATION or PRODUCTION. |
