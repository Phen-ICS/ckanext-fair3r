# Operations

## Configuration (`ckan.ini`)

| Setting | Default | Meaning |
|---|---|---|
| `ckanext.fair3r.context` | `DEV` | `DEV`, `INTEGRATION`, `VALIDATION` or `PRODUCTION`. A badge with the name shows in the header, except in production. `PRODUCTION`: `/dataset/new` opens the FDF form directly. |
| `ckanext.fair3r.enable_fdf_integration` | `true` | `false`: `/dataset/new` opens CKAN's standard form |
| `ckanext.fair3r.fdf_schema_dir` | - | Directory containing `fdf_schema.json` and `i18n/`, used instead of the package's copy (local schema work); also `CKANEXT_FAIR3R_FDF_SCHEMA_DIR`. Ignored if it has no `fdf_schema.json`. |
| `ckanext.contact.mail_to` | `smtp.mail_from` | Recipient of account requests |

For the RDF output (with ckanext-dcat):

```ini
ckanext.dcat.rdf.profiles = fair3r_dcat_ap
ckanext.dcat.croissant.profiles = fair3r_croissant
ckanext.dcat.structured_data.profiles = fair3r_schemaorg
```

Also read: `ckan.site_url` (sitemap, emails, local subject-scheme URIs),
`ckan.site_title`, `smtp.*`, `ckan.redis.url` (draft guard, account
request limit). When ckanext-zenodo is enabled, its routing in the
resource form uses `ckan.max_resource_size` and `ckanext.xloader.formats`.

Plugin order in `ckan.plugins`: the first-listed plugin's templates win,
and this plugin's `header.html` replaces CKAN's rather than extending it -
keep `pages` **before** `fair3r`, or the Pages and Blog links disappear.

## Command

| Command | Use |
|---|---|
| `ckan fair3r update-schema` | Download the FDF schema and its French translation from GitHub into the package (daily cron). Prints the schema version; exits non-zero if the schema can't be fetched or written. With `fdf_schema_dir` set, reads the local schema instead and downloads nothing. |

The CKAN user needs write access to the package's
`ckanext/fair3r/schema/` directory (the servers' deploy and the DEV
entrypoint set it).

## Deployment

**DEV (Docker Compose, fair3r-docker-alt)**: the repository is mounted in
the container and installed in editable mode; `ckan/scripts/entrypoint.sh`
writes `ckanext.fair3r.context` from `FAIR3R_CONTEXT`, and
`fdf_schema_dir = /fdf-schema` when the clone of fair3r-fdf-schema named
by `FDF_SCHEMA_LOCAL_PATH` is mounted there. After a Python change:
`supervisorctl -c /etc/supervisor/conf.d/ckan-supervisord-dev.conf restart all`
in the container.

**integration / validation / production (Ansible, fair3r-docker-alt)**:
the package is installed from PyPI; `ckanext.fair3r.context` is the
environment name in upper case; `update-schema` runs at deploy time and
daily at midnight (cron, CKAN user). The plugin list is
`ckan_extra_plugins` in `deploy/ansible/group_vars/all.yml`.

**CI**: every merge to `main` publishes the package to PyPI (the version
in `setup.py` must change - checked on each MR). An MR triggers the
integration deploy and the `test:integration:fair3r` job in
fair3r-docker-alt with that MR's own build. Tests on the server use the `test.ini` shipped in the
package; in DEV, the repository root `test.ini` - keep their plugin lists
in sync.

## Translations

Source strings are English; the French catalogue is
`ckanext/fair3r/i18n/fr/LC_MESSAGES/ckanext-fair3r.po`. After changing
user-facing text in Python, templates or JavaScript:

```shell
python setup.py extract_messages
python setup.py update_catalog -l fr
# translate the new or fuzzy entries in the .po
python setup.py compile_catalog
```

Commit the `.pot`, `.po` and `.mo`. Entries marked `fuzzy` aren't used
until reviewed. A CKAN core string missing from CKAN's French catalogue
can be translated here: add it to `lib/admin_i18n.py`, extract, translate.

The FDF schema's own texts are translated in the fair3r-fdf-schema
repository (`i18n/fr.json`), not here.

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| FDF form empty, or "Invalid or missing FDF schema" | Schema file missing or invalid JSON | `ckan fair3r update-schema`; check `fdf_schema_dir`; CKAN log ("Failed to load FDF schema") |
| Form labels in English on the French site | `schema/i18n/fr.json` missing or older than the schema | `ckan fair3r update-schema` (its output lists the translation update) |
| `update-schema`: permission denied | CKAN user can't write the package's `schema/` directory | Fix the directory's owner (the deploy does it) |
| Saving says "Missing FDF metadata payload" | The form's JavaScript didn't run (blocked asset, script error) | Browser console; reload with the cache cleared |
| A just-finished dataset is back to draft | xloader race, and the guard couldn't act | Is the worker running? Redis reachable? Log line "reverted to draft within" |
| "Publish" fails with a DataCite message | ckanext-doi refused the metadata (e.g. no creator) | Fix the FDF answers; the dataset stays private |
| No DOI on the dataset page | ckanext-doi not enabled, or the DOI not yet registered | Enable/configure ckanext-doi; see its logs |
| Account request: "please try again later" | 20 requests this hour, or the mail server refused | CKAN log: "hourly limit reached" or the mail error |
| No FDF data in `/dataset/<id>.rdf` or the page's JSON-LD | Profiles not configured, or the dataset has no `datacite.*` extras (not saved with the FDF form) | Settings above; save the dataset with the FDF form once |
| Gene search for Xenopus slow or without line types | Xenbase slow: the line types stop after 15 s | Expected; retry later |
| Activity page "no permission" for a member | User not a member of that organization/group | Add them; sysadmins always see it |
