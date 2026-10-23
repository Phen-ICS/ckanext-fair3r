# Architecture

## Components

```
Browser
  FDF form (assets/js/fdf-form.js, built from window.FDF_SCHEMA)
    |  searches ORCID, ROR, OLS, ChEBI, MyGene, Ensembl, Alliance directly
    |  POST /dataset/new/fdf or /dataset/edit/<id>  (fdf_output_json + CKAN fields)
    v
CKAN web process - blueprints/fdf.py, lib/fdf/render.py
    |  validation.py (schema rules) -> package.py / extras.py
    |  (fdf_output_json, datacite.* extras, author/maintainer)
    v
package_create / package_patch  --> ckanext-doi hook: DataCite DOI
                                     (metadata via this plugin's IDoi methods)

Resource form (public/base/js/resource-upload.js)
    |  resource_create per file (XHR, progress), or /zenodo/upload/... (ckanext-zenodo)
    |  "Finish": package_revise(state=active)
    v
after_dataset_update -> draft_guard.py -> RQ job if a stale "draft" overwrote "active"

Dataset page: fdf_metadata_display.html (sections), completeness, "Publish", "Download all"
ckanext-dcat: /dataset/<id>.<format>, JSON-LD in the page -> this plugin's RDF profiles
cron: ckan fair3r update-schema (daily) -> schema/fdf_schema.json + schema/i18n/fr.json
```

## CKAN interfaces

Declared in `plugin.py` (`Fair3RPlugin`):

| Interface | Used for |
|---|---|
| `IConfigurer` | Template and public directories, the `fair3r` webassets; replaces CKAN's password-reset and invitation mail functions with HTML versions (`lib/mailer.py`) |
| `ITemplateHelpers` | Helpers listed below |
| `IBlueprint` | Routes listed below |
| `IActions` | `fdf_completeness` |
| `IAuthFunctions` | Auth of that action; chained `organization_activity_list` / `group_activity_list` (only when the `activity` plugin is loaded - chaining onto a missing action stops CKAN from starting) |
| `IPackageController.after_dataset_update` | `draft_guard.py` |
| `IDoi` (ckanext-doi) | `build_metadata_dict`, `build_xml_dict`: DataCite metadata from the `datacite.*` extras |
| `IFacets` | "Licenses" facet title translated (CKAN's French catalogue misses it) |
| `IClick` | `ckan fair3r update-schema` |
| `ITranslation` | English source strings, French catalogue in `i18n/` |

RDF profiles are entry points (`setup.py`, `ckan.rdf.profiles`), not a
plugin interface: `fair3r_dcat_ap`, `fair3r_croissant`, `fair3r_schemaorg`.

## Routes

| Route | Module | What |
|---|---|---|
| `GET /dataset/new` | `blueprints/dataset_choice.py` | Choice between FDF and the standard form; FDF directly in PRODUCTION; standard form if `enable_fdf_integration` is false. Not logged in: redirect to `/account/request`. |
| `GET/POST /dataset/new/fdf` | `blueprints/fdf.py` | FDF creation form |
| `GET/POST /dataset/new/standard` | `blueprints/standard_creation.py` | CKAN's own creation form (`CreateView`) |
| `GET/POST /dataset/edit/<id>` | `blueprints/fdf.py`, `lib/fdf/render.py` | FDF edit form for FDF datasets (needs `package_update`), CKAN's edit view otherwise |
| `POST /dataset/<id>/publish` | `blueprints/publish.py` | `package_patch(private=False)` |
| `GET /dataset/<id>/download-all` | `blueprints/download_all.py` | ZIP of CKAN-stored files + metadata summary; Zenodo's ZIP if only Zenodo files |
| `GET/POST /account/request` | `blueprints/account_request.py` | Account request form (emails the admins). Also an app-wide 403 handler that sends visitors refused dataset creation here. |
| `GET /sitemap.xml` | `blueprints/sitemap.py` | Home, dataset list, organizations, public datasets |
| (before every request) | `blueprints/activity_guard.py` | Friendly "members only" page on org/group activity streams |

## Actions

| Action | Auth | What |
|---|---|---|
| `fdf_completeness` | Logged in | Completeness of the form being edited, from the live form values (`fdf_output_json`, `title`, `notes`, `tag_string`, `license_id`) |

## Template helpers

| Helper | Returns |
|---|---|
| `fdf_schema`, `fdf_schema_sections` | The localized FDF schema; its sections shown on the dataset page |
| `parse_fdf_json`, `extract_fdf_section_data` | Parsed answers; the data of one section through its `display_mapping` |
| `fdf_split_symbol_sup` | Gene/allele symbol split into base and superscript (`Apoe<sup>tm1Unc</sup>`), rendered without trusting the HTML |
| `fair3r_completeness`, `fair3r_show_completeness_row` | Completeness of a dataset; whether to show it in "Additional info" (not when ckanext-citations shows it) |
| `fair3r_context`, `fair3r_is_superadmin`, `fair3r_is_authenticated`, `fair3r_current_user`, `fair3r_is_resource_read` | Environment and user state for templates |
| `fair3r_license_options`, `fair3r_member_count_label` | Licence list with acronyms; "N members" label |
| `fair3r_zenodo_routing_config`, `fair3r_doi_url`, `fair3r_zenodo_files_archive_url` | ckanext-zenodo integration (`lib/zenodo_routing.py`); `None` when zenodo isn't enabled |

## Modules

| Module | Responsibility |
|---|---|
| `plugin.py` | Interfaces above; the `IDoi` metadata merge |
| `blueprints/*` | Routes above |
| `lib/actions.py` | `fdf_completeness` and its auth |
| `lib/fdf/schema.py`, `schema_i18n.py` | Load the FDF schema and apply its French sidecar |
| `lib/fdf/validation.py` | Server-side checks of `fdf_output_json` against the schema |
| `lib/fdf/form.py`, `package.py`, `extras.py`, `tags.py` | Build the `package_create`/`package_patch` payload from the form |
| `lib/fdf/converter.py` | Author/maintainer from the FDF creators |
| `lib/fdf/datacite_converter.py` | FDF -> DataCite (the `datacite.*` extras; also a standalone DataCite XML builder used by tests) |
| `lib/fdf/completeness.py` | Completeness score |
| `lib/fdf/render.py`, `context.py`, `options.py` | FDF create/edit views and their template variables |
| `lib/fdf/draft_guard.py` | Self-healing of the xloader "back to draft" race |
| `lib/fdf/dcat_ap_profile.py`, `croissant_profile.py`, `schemaorg_profile.py`, `schemaorg_fields.py`, `rdf_extras.py` | RDF profiles |
| `lib/zenodo_routing.py` | Soft integration with ckanext-zenodo |
| `lib/mailer.py` | HTML password-reset and invitation emails |
| `lib/admin_i18n.py` | CKAN core strings missing from CKAN's French catalogue, for extraction |
| `tasks.py`, `cli.py` | `update-schema` |
| `assets/js/fdf-form.js` | The FDF form (CKAN JS module `fdf-form-module`) |
| `public/base/js/resource-upload.js` | Resource form: progress, several files, duplicate-name warning, Zenodo routing, activation |

## What's stored

No table of its own. Everything is on the dataset:

| Where | What |
|---|---|
| Extra `fdf_output_json` | The FDF answers (marks the dataset as an FDF dataset) |
| Extras `datacite.*` | DataCite fields derived from it, rewritten on every FDF save |
| `author`, `author_email`, `maintainer`, `maintainer_email` | From the FDF creators |
| Redis `fair3r:recently_activated:<id>` (120 s) | Datasets just seen active, for `draft_guard.py` |
| Redis `fair3r:account_requests:<hour>` | Account requests this hour |

## Templates overridden (main ones)

| Template | Change |
|---|---|
| `base.html`, `page.html`, `header.html`, `footer.html`, `home/*` | Theme; header with the environment badge, Pages/Blog links (ckanext-pages), admin icons |
| `package/new_fdf.html`, `package/edit_fdf.html`, `package/edit.html`, `package/snippets/package_form.html` | FDF form pages |
| `package/creation_choice.html` | FDF / standard choice |
| `package/read_base.html` | "Publish" and "Download all" buttons |
| `package/snippets/additional_info.html`, `package/snippets/fdf_metadata_display.html` | FDF answers on the dataset page, completeness |
| `snippets/package_item.html`, `snippets/package_list.html`, `snippets/activities/*` | Search results, activity stream items |
| `organization/activity_forbidden.html`, `group/activity_forbidden.html` | "Members only" page |
| `account/request_account.html` | Account request form |
| `emails/html/*` | HTML emails |

## Dependencies on other extensions

| Extension | Used for | Without it |
|---|---|---|
| ckanext-doi (PyPI `ckanext-fair3r-doi`) | **Must be installed** (`IDoi` is imported). Enabled: DOI minting with FDF metadata. | Installed but not enabled: no DOI, everything else works |
| ckanext-dcat (`dcat`, `structured_data`, `croissant`) | Loads the RDF profiles | No RDF output |
| CKAN `activity` | Members-only activity streams | Nothing to restrict |
| ckanext-xloader | Its race is what `draft_guard.py` fixes | Guard never triggers |
| ckanext-pages | Pages/Blog links in the header (keep `pages` before `fair3r` in `ckan.plugins`) | No such links |
| ckanext-citations | Shows the completeness score in its "FAIR & Impact" panel | Score shown in "Additional info" |
| ckanext-zenodo | Large/non-tabular files on Zenodo; routing in the resource form; Zenodo ZIP in "Download all" | Every file stays in CKAN |
| ckanext-contact | `ckanext.contact.mail_to`, the account requests' recipient | Falls back to `smtp.mail_from` |
