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

- **FDF form**: dataset creation and editing with a form generated from
  [fdf_schema.json](https://github.com/Phen-ICS/fair3r-fdf-schema), which
  looks terms up in external databases (ORCID, ROR, ontologies, genes,
  alleles, strains) and is checked again on the server. The answers are
  stored on the dataset (`fdf_output_json`) with DataCite-shaped
  `datacite.*` extras derived from them.
- **Completeness score** on the dataset page and live in the form.
- **Metadata for other systems**: DataCite DOI metadata through
  ckanext-doi, DCAT-AP, Croissant and schema.org through ckanext-dcat, a
  sitemap.
- **Publishing and downloading**: a "Publish" button (private -> public,
  one way), "Download all" as one ZIP, a fix for a CKAN/xloader race that
  can turn a just-published dataset back to draft.
- **Resource form**: several files at once with progress, duplicate-name
  warning, routing of large files to Zenodo with
  [ckanext-zenodo](https://github.com/Phen-ICS/ckanext-zenodo).
- **Accounts and access**: account request form, members-only
  organization/group activity streams, HTML emails.
- **Theme** of fair3r.fr, French translations.

The full specification is in [docs/](https://github.com/Phen-ICS/ckanext-fair3r/blob/main/docs/README.md): architecture, the
FDF schema, every workflow step by step, metadata mapping, security,
configuration and operations.

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
| `ckanext.fair3r.fdf_schema_dir` | (the copy in the package) | A directory with `fdf_schema.json` and `i18n/*.json`, used instead of the package's copy (for working on the schema locally); also read from `CKANEXT_FAIR3R_FDF_SCHEMA_DIR`. |
| `ckanext.contact.mail_to` | `smtp.mail_from` | Who receives account requests. |

More in [docs/operations.md](https://github.com/Phen-ICS/ckanext-fair3r/blob/main/docs/operations.md), with troubleshooting.

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

English source strings, French catalogue in `ckanext/fair3r/i18n/fr/`:
see [docs/operations.md](https://github.com/Phen-ICS/ckanext-fair3r/blob/main/docs/operations.md#translations) for the
extract / update / compile steps.

## License

Released under the GNU Affero General Public License (AGPL) v3.0. See the
file `LICENSE` for details.
