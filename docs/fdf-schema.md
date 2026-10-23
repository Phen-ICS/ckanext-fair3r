# The FDF schema

The form is not hard-coded: `fdf-form.js` builds it from `fdf_schema.json`,
and the server validates, scores and displays the answers from the same
file. The schema is maintained in
[fair3r-fdf-schema](https://github.com/Phen-ICS/fair3r-fdf-schema) and
not included in this package: `ckan fair3r update-schema` downloads it
into the package's `schema/` directory (ignored by git). Its own
description: "100% declarative schema.
All business logic, APIs, conditions and output mapping are here."

## Top-level keys

| Key | Content |
|---|---|
| `version`, `meta` | Schema version (e.g. 3.0.4), title, changelog, default publisher |
| `sections` | The form, in order |
| `apis` | External search APIs the fields use, with a declarative `mapper` that turns their results into `{id, label, sublabel, scheme...}` |
| `vocabularies` | Fixed lists: `organism_presets` (organisms offered first, with their NCBI taxon), `credit_roles` (CRediT contributor roles), `xenbase_line_types` |
| `xref_catalog` | Model-organism databases (MGI, RGD, ZFIN, FlyBase, Xenbase, WormBase, Ensembl) a gene or allele can be cross-referenced to |

## Sections

| Key | Meaning |
|---|---|
| `id`, `title`, `icon` | Identity and heading |
| `fields` | The section's fields |
| `repeatable`, `initial_instances`, `add_label`, `repeat_label` | The section can be added several times (several genes, several creators...) |
| `condition` | Shown only when another answer allows it: `checkbox_includes` (e.g. the Genes section only when "Genetic modification" is ticked among the interventions), `organism_trigger` (the Strain section, driven by the chosen organism) |
| `output.mode = collect_object`, `output.path` | Each instance becomes one object of a list (e.g. `creators[]`) |
| `subject_scheme` | Scheme of the subjects the section produces |
| `display_mapping` | How the dataset page shows the section: `source` (answer key or list of keys), `filter` (e.g. `subjectScheme: NCBITaxon`), labels, colour, display type |
| `show_in_dataset` | `false`: not shown on the dataset page |
| `open_default` | Section expanded when the form opens |

Sections in schema 3.0.4: title, related identifiers, publisher, creators,
contributors, biological model (organism), strain, interventions, genes,
chemicals, diet, disease, anatomy.

## Fields

| Key | Meaning |
|---|---|
| `type` | `text`, `number`, `select`, `checkbox_group`, `multi_select`, `preset_or_search` (a list of presets plus a search, e.g. organism), `api_search` (search an external API) |
| `required`, `min`, `max`, `max_length`, `pattern` | Checks, done in the browser and again on the server |
| `api`, `search_api`, `api_by_taxon`, `api_fallback` | Which API to search; `api_by_taxon` picks one per organism (MGI for mouse, RGD for rat, ZFIN for zebrafish...) |
| `depends_on`, `dependent_on_field`, `use_organism_taxon`, `organism_dependent` | The search needs another answer first (e.g. alleles of the chosen gene) |
| `allow_manual` | Free text accepted when the API has nothing; such values aren't required to have a URI |
| `autofill_from`, `autofill_label_to`, `orcid_autofill_from`, `bind_to`, `update_display_field` | Fill other fields from a selected result (e.g. name and affiliation from an ORCID) |
| `visible_if` | `{field, value}`, `{field, not_empty[, taxon_in / taxon_not_in]}`, `{field, checked}` |
| `on_change`, `clear_dependent_fields` | Reset dependent fields when this one changes |
| `show_xrefs`, `xref_concept` | Also store the cross-references of a gene/allele (see below) |
| `output` | Where the answer goes in `fdf_output_json` |

### Output

| Key | Meaning |
|---|---|
| `path` | Key in the answers (`publicationYear`, `subjects`, `relatedIdentifiers`...) |
| `mode` | `set`, `set_int`: the value; `append`, `append_if`, `append_from_array`: add an entry to a list; inside a `collect_object` section, `obj_key` names the key in the instance's object |
| `tpl` | Template of the entry added, e.g. `{"subject": "$label", "subjectScheme": "NCBITaxon", "valueURI": "$id"}` - `$label`, `$id`, `$scheme` come from the selected API result |
| `also_description` | Also mention the value in the generated description |

Most biological answers end up as **subjects**: organism (`NCBITaxon`),
strain (EFO), gene (`geneAccessionId`), allele (`alleleAccessionId`),
mutation type, chemicals (ChEBI), diet (EFO), disease (MONDO) and its
phenotypes (uPheno), tissue (UBERON). A gene's or allele's cross-references are extra
subjects with their own provider as `subjectScheme` (e.g. `MGI`) and
`crossRefOf` naming the primary scheme; the dataset page shows them with
the identifier they belong to.

## External APIs

Called **from the browser**, directly: ORCID, ROR, EBI OLS (NCBITaxon,
EFO, uPheno, MONDO, UBERON), ChEBI, MyGene.info, Ensembl, Alliance of
Genome Resources. The server makes none of these calls.

The Xenopus strain/line is typed in by hand: Xenbase blocks automated
access to its line pages (reCAPTCHA) and publishes no API or file for its
lines. The Xenopus gene itself is found through MyGene.info.

## Translations

The schema is written in English. French strings live next to it in
`i18n/fr.json` (same repository), keyed by path. `schema_i18n.py` applies
them to `title`, `label`, `placeholder`, `help_text` and `help` when the
page language is French; everything else (ids, values, URIs) stays as is.

## Loading and updating

- `load_fdf_schema()` reads the file on every call (about 0.6 ms) and
  applies the translation for the current request's language. An invalid
  or missing file gives an empty form (logged), not an error page.
- Where it's read from: `ckanext.fair3r.fdf_schema_dir` (or the
  `CKANEXT_FAIR3R_FDF_SCHEMA_DIR` environment variable) when it points at
  a directory containing `fdf_schema.json`; otherwise the package's
  `schema/` directory, where `update-schema` writes it.
- `ckan fair3r update-schema` downloads `fdf_schema.json` and
  `i18n/fr.json` from the `main` branch on GitHub and writes them into the
  package directory (atomically: temporary file, then rename). A failed
  translation download keeps the previous one. With a local schema
  directory configured (DEV), nothing is downloaded.
- On the servers it runs at deploy time and daily at midnight (cron).
  The schema version shown in the command's output is the file's
  `version`.

Changing the schema changes the form for new and edited datasets at the
next page load. Existing answers aren't migrated: a renamed `path` or
`obj_key` leaves old answers where they were. `fdf-form.js` keeps a
small compatibility list for older subject labels
(`LEGACY_SUBJECT_PREFIXES`).
