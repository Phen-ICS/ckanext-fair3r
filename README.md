<table>
<tr>
<td width="150">
  <img alt="Fair3R logo" src="https://fair3r.fr/base/images/fair3r_logo.png" width="150">
</td>
<td>

# ckanext-fair3r

![CKAN](https://img.shields.io/badge/CKAN-2.12.0-orange)
![License](https://img.shields.io/badge/license-AGPL--3.0-blue)
[![PyPI](https://img.shields.io/pypi/v/ckanext-fair3r)](https://pypi.org/project/ckanext-fair3r/)

</td>
</tr>
</table>

The CKAN plugin behind [fair3r.fr](https://fair3r.fr), a catalogue of
research datasets (animal models, phenotyping). It adds the **FDF**
(FAIR3R Dataset Form): a dynamic, ontology-driven metadata form built from
a JSON schema. It turns those metadata into DataCite, DCAT-AP, Croissant
and schema.org, and gives the site its theme and a few features around
datasets.

For a ready-to-run FAIR3R stack with this plugin already wired up, see
[fair3r-docker-alt](https://github.com/Phen-ICS/fair3r-docker-alt). The
rest of this page is for adding the plugin to your own CKAN 2.12.

## Features

**Creating and editing datasets**

- `/dataset/new` offers a choice between the FDF and CKAN's standard
  form. With `ckanext.fair3r.context = PRODUCTION` it opens the FDF form
  directly. Visitors who aren't logged in are sent to the account
  request page.
- The FDF form (`/dataset/new/fdf`) is generated from
  [fdf_schema.json](https://github.com/Phen-ICS/fair3r-fdf-schema). It
  searches external databases for genes, alleles, strains, organisms and
  ontology terms, and is checked again on the server: required fields,
  vocabularies, formats, duplicate people, controlled subjects.
- The FDF answers are stored on the dataset as the `fdf_output_json` extra,
  with derived `datacite.*` extras, and they fill CKAN's author and
  maintainer fields.
- `/dataset/edit/<id>` opens the FDF form for datasets created with it,
  and CKAN's own form for the others. Editing requires the right to
  update the dataset.
- A completeness score is shown on the dataset page and updates live
  in the form (`fdf_completeness` action). When ckanext-citations is
  enabled, the score appears in its "FAIR & Impact" panel instead.
- `external_lookup` action: server-side lookups the form can't make from
  the browser (Xenbase lines, RGD variants). Logged-in users only, and
  only to those two hosts.
- Resource form: several files at once, a progress bar, a warning when a
  file name already exists in the dataset. When
  [ckanext-zenodo](https://github.com/Phen-ICS/ckanext-zenodo) is set up,
  large or non-tabular files are sent to Zenodo instead of CKAN storage.

**Metadata for other systems**

- DataCite: through ckanext-doi's `IDoi` interface, the DOI metadata is
  built from the FDF answers (creators with ORCID and ROR, contributors,
  subjects, related identifiers).
- RDF profiles for ckanext-dcat: `fair3r_dcat_ap`, `fair3r_croissant`,
  `fair3r_schemaorg` (the schema.org one is also embedded in dataset
  pages by DCAT's `structured_data` plugin).
- `/sitemap.xml`: home page, organizations and public datasets.

**Publishing and downloading**

- "Publish" button on the dataset page (`POST /dataset/<id>/publish`):
  makes a private dataset public in one step (and, with ckanext-doi
  enabled, mints its DOI).
  It only works in that direction; making a dataset private again stays a
  Manage -> Visibility edit.
- "Download all" (`/dataset/<id>/download-all`): one ZIP with the files
  stored in CKAN and a metadata summary. Files stored on Zenodo are
  offered as Zenodo's own ZIP.
- Self-heals a CKAN/xloader race that can silently turn a just-published
  dataset back to draft (`lib/fdf/draft_guard.py`).

**Accounts and access**

- `/account/request`: a form that emails the administrators, limited to
  20 requests per hour for the whole site.
- Organization and group activity streams are visible to members only,
  on the pages and through the API (when CKAN's `activity` plugin is on).
- Password reset and invitation emails in HTML.

**Theme**

- Templates for the header, footer, home page and dataset pages, with a
  badge showing the environment (DEV, INTEGRATION, VALIDATION).
- Short licence names (CC BY, ODbL...) in licence lists.
- French translations, including CKAN core strings its own French
  catalogue leaves untranslated (`lib/admin_i18n.py`).

## Requirements

- CKAN 2.12, with Redis and the background worker (`ckan jobs worker`)
  running: they're used to fix the draft race and to limit account
  requests.
- **[ckanext-doi](https://github.com/Phen-ICS/ckanext-doi)**, FAIR3R's
  fork, published on PyPI as `ckanext-fair3r-doi` (the `ckanext-doi`
  package on PyPI is a different one, the original). It must be
  **installed**, since this plugin uses its interface. Enabling it (and
  having a DataCite account) is only needed to mint DOIs.
- Optional, each one adds something when enabled:

  | Plugin | Adds |
  |---|---|
  | `dcat`, `structured_data`, `croissant` ([ckanext-dcat](https://github.com/ckan/ckanext-dcat)) | The FAIR3R RDF profiles |
  | `activity` (CKAN core) | Members-only activity streams |
  | `pages` ([ckanext-pages](https://github.com/Phen-ICS/ckanext-pages), PyPI: `ckanext-fair3r-pages`) | Pages and Blog links in this plugin's header |
  | `citations` ([ckanext-citations](https://github.com/Phen-ICS/ckanext-citations)) | The "FAIR & Impact" panel, with the completeness score |
  | `zenodo` ([ckanext-zenodo](https://github.com/Phen-ICS/ckanext-zenodo)) | Large files on Zenodo, with a DOI |
  | `contact` ([ckanext-contact](https://github.com/NaturalHistoryMuseum/ckanext-contact)) | The contact page; its `ckanext.contact.mail_to` is where account requests go |

## Installation

1. In CKAN's virtualenv:

   ```shell
   pip install ckanext-fair3r ckanext-fair3r-doi
   ```

2. Enable the plugin in `ckan.ini`. The first-listed plugin's templates
   win, and this plugin's header replaces CKAN's: keep `pages` before
   `fair3r`, or the Pages and Blog links disappear.

   ```ini
   ckan.plugins = ... dcat structured_data croissant pages fair3r doi citations ...
   ```

3. Optional, for the FAIR3R RDF output (with ckanext-dcat):

   ```ini
   ckanext.dcat.rdf.profiles = fair3r_dcat_ap
   ckanext.dcat.croissant.profiles = fair3r_croissant
   ckanext.dcat.structured_data.profiles = fair3r_schemaorg
   ```

4. Fetch the latest FDF schema, and keep it up to date daily, as the CKAN
   user (cron). A copy of the schema ships with the package, so the form
   works before the first update.

   ```cron
   0 0 * * * /path/to/venv/bin/ckan -c /path/to/ckan.ini fair3r update-schema
   ```

   The CKAN user needs write access to the package's
   `ckanext/fair3r/schema/` directory.

5. Restart CKAN and its worker.

## Configuration

| Setting | Default | Meaning |
|---|---|---|
| `ckanext.fair3r.context` | `DEV` | `DEV`, `INTEGRATION`, `VALIDATION` or `PRODUCTION`. Shown as a badge in the header (except in production). `PRODUCTION`: `/dataset/new` opens the FDF form directly, without the choice page. |
| `ckanext.fair3r.enable_fdf_integration` | `true` | `false`: `/dataset/new` opens CKAN's standard form. |
| `ckanext.fair3r.fdf_schema_dir` | (the copy in the package) | A directory with `fdf_schema.json` and `i18n/*.json`, used instead of the package's copy; `update-schema` then downloads nothing. For working on the schema locally (a clone of [fair3r-fdf-schema](https://github.com/Phen-ICS/fair3r-fdf-schema)). Also read from the `CKANEXT_FAIR3R_FDF_SCHEMA_DIR` environment variable. |
| `ckanext.contact.mail_to` | `smtp.mail_from` | Who receives account requests. |

Also used from CKAN's own settings: `ckan.site_url` and `ckan.site_title`
(emails, sitemap), the `smtp.*` settings (emails).

## Commands

| Command | Use |
|---|---|
| `ckan fair3r update-schema` | Download the latest `fdf_schema.json` and its French translations from GitHub into the package (daily cron). Does nothing when `fdf_schema_dir` points to a local clone. |

## Development

```shell
git clone https://github.com/Phen-ICS/ckanext-fair3r.git
cd ckanext-fair3r
pip install -e .
pip install -r dev-requirements.txt
```

Code style, checked in CI (ruff 0.16.0):

```shell
ruff format ckanext
ruff check ckanext --fix
```

### Tests

```shell
docker exec -u ckan -it ckan-app pytest --ckan-ini=/plugins/ckanext-fair3r/test.ini /plugins/ckanext-fair3r/ckanext/fair3r/tests
```

Always pass `--ckan-ini`: the test fixtures empty the database they run
against, and refuse to run unless its name contains `test`. The
`test.ini` at the repository root is for the DEV container;
`ckanext/fair3r/tests/test.ini`, shipped in the package, is the one the
integration server uses - keep their plugin lists in sync.

### Translations

The source strings are English; the French catalogue is in
`ckanext/fair3r/i18n/fr/`. After changing user-facing text (Python,
templates or JavaScript):

```shell
python setup.py extract_messages
python setup.py update_catalog -l fr
# translate the new entries in ckanext/fair3r/i18n/fr/LC_MESSAGES/ckanext-fair3r.po
python setup.py compile_catalog
```

Commit the `.pot`, `.po` and `.mo` files. To translate a CKAN core string
its French catalogue misses, add it to `lib/admin_i18n.py`.

## License

Released under the GNU Affero General Public License (AGPL) v3.0. See the
file `LICENSE` for details.
