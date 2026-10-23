# Workflows

Each section describes one action as the user sees it, then what happens
on the server.

## 1. Creating a dataset

### Choosing the form - `GET /dataset/new`

- Not logged in: redirected to `/account/request` (section 8). A
  logged-in user that CKAN refuses dataset creation to (no organization)
  is also sent there, by an app-wide 403 handler on `/dataset/new*`.
- `ckanext.fair3r.enable_fdf_integration = false`: CKAN's standard form.
- `ckanext.fair3r.context = PRODUCTION`: the FDF form directly.
- Otherwise: a page offering the FDF form or CKAN's standard form
  (`/dataset/new/standard`).

### Filling the FDF form - `/dataset/new/fdf`

The page holds CKAN's usual fields (title, URL, description, tags,
licence, organization, visibility) and the FDF form below them.
`fdf-form.js` builds the form from the schema (see
[fdf-schema.md](fdf-schema.md)):

- sections open and close as answers change (the Genes section appears
  when "Genetic modification" is ticked, the Strain section once an
  organism is chosen...);
- search fields query external databases as the user types and fill
  related fields from the chosen result (an ORCID fills the name and
  affiliation; a gene restricts the allele search);
- the completeness score updates live, through the `fdf_completeness`
  action;
- on submit, the answers are written as one JSON document into the hidden
  `fdf_output_json` field, after the same checks the server runs.

### Saving - `POST /dataset/new/fdf`

1. **Validate** `fdf_output_json` against the schema (`validation.py`):
   - required fields of every section that applies (a section whose
     `condition` is false, or a field whose `visible_if` is false, is
     skipped); at least one instance of a required repeatable section;
   - `select`, `multi_select` and `checkbox_group` values among the
     allowed options/vocabulary;
   - `pattern` formats;
   - no duplicate creator (same given name, family name and email), no
     duplicate contributor;
   - controlled subjects: a subject from an API field must carry a valid
     URI of the right shape for its API, unless the field allows manual
     entry.
   Any error: the form is shown again with the messages, nothing saved.
2. **Build the dataset**: CKAN's fields from the form, plus:
   - extra `fdf_output_json` (the answers as submitted);
   - `datacite.*` extras derived from it (see
     [metadata-mapping.md](metadata-mapping.md)); a conversion error is
     logged and leaves them out, it doesn't block the save;
   - `author` / `author_email` and `maintainer` / `maintainer_email`
     from the creators.
3. **`package_create`** with `state = draft`.
4. Redirect to the "add resource" page.

## 2. Adding files

The resource form is CKAN's, enhanced by `resource-upload.js`:

- **Progress**: a file is sent with `resource_create` through
  XMLHttpRequest, with a progress bar, instead of a plain form post.
- **Several files at once**: each becomes its own resource, named after
  its file, sharing the description typed; each result (success or error)
  is listed as it finishes. On any failure the dialog stays open so
  nothing typed is lost.
- **Same name warning**: a file whose name already exists in the dataset
  is flagged before upload ("adds a second copy" in CKAN; "replaces it"
  for a file already on Zenodo).
- **Zenodo**: when ckanext-zenodo is enabled with a token, files larger
  than `ckan.max_resource_size` or not readable by the data viewer (or
  with "Zenodo" switched on) go to ckanext-zenodo's upload endpoint
  instead. See that plugin's documentation.
- **Finish**: the dataset is made active with `package_revise`
  (`state = active`). `package_revise` locks the row while it reads it,
  unlike `package_patch`, whose read can return a stale cached copy and
  write "draft" back.

### The "back to draft" race - `draft_guard.py`

xloader updates a resource from its own background job, and CKAN's
`resource_patch` re-saves the *whole* dataset it read. If that read
happened before "Finish" and the write after it, the dataset silently
goes back to draft. The guard runs on every dataset update:

- a dataset seen **active** is remembered in Redis for 120 seconds;
- if it's then saved as **draft** within that window, a background job
  sets it back to active (`package_revise`, with auth ignored).

It's a background job because the hook runs inside the caller's own
transaction, where `package_revise` can't commit. Needs Redis and the
worker.

## 3. Editing - `/dataset/edit/<id>`

- FDF dataset (has `fdf_output_json`): the FDF form, prefilled from the
  stored answers. Only users who may update the dataset get it (403
  otherwise). Saving runs the same checks and build as creation, then
  `package_patch` (so the resources are kept).
- A draft is saved as a draft and goes on to the "add resource" page.
- Any other dataset: CKAN's own edit view.

The stored answers are passed to the page as JSON-encoded values and the
form escapes every value it writes back into HTML (see
[security.md](security.md)).

## 4. Publishing - `POST /dataset/<id>/publish`

The "Publish" button (on an active private dataset's page, for users who
may update it) posts here through CKAN's confirmation dialog, which warns
that the DOI and the Zenodo record stay public for good:

1. `package_patch(private = False)` as the user (CKAN checks the right to
   update).
2. ckanext-doi's own `after_dataset_update` hook, in the same call, mints
   the DOI with the metadata this plugin builds (`IDoi`). ckanext-zenodo's
   hook queues the publication of the dataset's Zenodo files.
3. Success: "The dataset is now public." Failure (e.g. ckanext-doi
   refusing incomplete metadata): the change is rolled back and the
   message says why; the dataset stays private.

Once public, the button becomes a "Published" badge, linking to the DOI
when DataCite has registered it.

Publishing is one-way on purpose (DOI, Zenodo record): making a dataset
private again is a deliberate Manage -> Visibility edit. Making it public
any other way (Manage, bulk actions, API) triggers the same hooks.

Later edits of a public dataset update its DataCite metadata the same way
(ckanext-doi compares and only sends a change).

## 5. Viewing a dataset

- **FDF answers**: `fdf_metadata_display.html` shows each section with
  `show_in_dataset` not false, using its `display_mapping` (which answers,
  which subjects by scheme, labels, colour). Gene and allele symbols with
  a superscript are rendered as such, without trusting stored HTML.
  Cross-references appear with the identifier they belong to. Empty rows
  (a related identifier or contributor with nothing in it) are skipped.
- **Completeness**: score and band in "Additional info", with what's
  missing - or in ckanext-citations' "FAIR & Impact" panel when it's
  enabled. Weights: required field 2, optional 1; CKAN's title (required),
  description, tags and licence count too. Red below 50, green from 80.
- **Machine-readable**: ckanext-dcat serves the dataset as DCAT-AP RDF,
  and embeds schema.org JSON-LD in the page, both with the FDF metadata
  (this plugin's profiles).

## 6. Downloading everything - `GET /dataset/<id>/download-all`

- Access as for the dataset page (`package_show` as the user).
- No file stored in CKAN: redirect to Zenodo's ZIP of the record when the
  dataset has Zenodo files, 404 otherwise.
- Otherwise a ZIP, built in a temporary file and deleted after sending:
  - `<dataset>-metadata.txt`: the dataset's fields, organization, tags,
    groups, extras and resource list;
  - each file stored in CKAN, under its file name; a second file with the
    same name gets `-2`, `-3`...; a file that can't be read is skipped
    (logged), it doesn't fail the archive.
- On the dataset page, "Download all" is one button, or a menu ("Catalogue
  files" / "Zenodo files") when the dataset has both kinds; Zenodo's ZIP
  is downloaded from Zenodo directly, never through the CKAN server.

## 7. Account request - `/account/request`

A public form: email, name, message. On submit:

1. All three required, or the form comes back.
2. At most 20 requests per hour for the whole site (Redis). Over it:
   "please try again later", nothing sent. If Redis is unavailable, the
   request goes through.
3. An email (text and HTML, the message rendered as Markdown, everything
   else escaped) to `ckanext.contact.mail_to`, falling back to
   `smtp.mail_from`.

## 8. Activity streams

Organization and group activity streams are **members only**
(sysadmins included), when CKAN's `activity` plugin is enabled:

- API (`organization_activity_list`, `group_activity_list`): a chained
  auth function refuses non-members; anonymous callers are refused
  before it runs.
- Pages (`/organization/activity/<id>`, `/group/activity/<id>`): the same
  rule, checked before the page renders, shows "You do not have
  permission to view this activity stream" instead of CKAN's bare 403.

Dataset and user activity streams are CKAN's, unchanged.
