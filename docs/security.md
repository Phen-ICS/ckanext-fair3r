# Security

## Who may do what

| Action | Rule |
|---|---|
| Create a dataset (`/dataset/new*`) | Logged in, plus CKAN's `package_create` (member of an organization with the right role). Refused users are sent to the account request page. |
| Edit with the FDF form (`/dataset/edit/<id>`) | CKAN's `package_update` on the dataset, checked before the form is shown (403 otherwise) and again by `package_patch` on save |
| Publish (`POST /dataset/<id>/publish`) | `package_update`, through `package_patch` as the user; CSRF-protected form post |
| Download all | `package_show` as the user: a private dataset's ZIP only for those who can see it |
| `external_lookup`, `fdf_completeness` | Logged-in users |
| Organization/group activity (pages and API) | Members of that organization/group, and sysadmins; anonymous refused |
| Account request | Anyone, 20 per hour for the whole site |
| `ckan fair3r update-schema` | Server shell (cron, as the CKAN user) |

Every POST form carries CKAN's CSRF token (`h.csrf_input()`); the
JavaScript calls to CKAN's API send it as `X-CSRFToken`.

## Stored values in pages

The FDF answers are free text written by editors, shown to every visitor
and, in the edit form, to other editors and sysadmins:

- On the dataset page they go through Jinja's normal autoescaping. Gene
  and allele symbols written by external databases with a superscript
  (`Apoe<sup>tm1Unc</sup>`) are recognised by shape and split into two
  plain-text parts that the template wraps in its own `<sup>`; any other
  markup is shown as text.
- In the edit pages they're passed to the JavaScript with `|tojson`,
  which escapes `<`, `>`, `&` and `'`, so a value can't close the
  `<script>` block.
- The form escapes every prefilled value it writes into its HTML
  (`_escapeHtml`, quotes included, for attribute values), and every label
  coming back from an external API.
- The account request email escapes the name, email and site title; the
  message is rendered with CKAN's Markdown renderer, which sanitizes HTML.

## External requests

- **From the browser** (the FDF form's searches): ORCID, ROR, EBI OLS and
  ChEBI, MyGene.info, Ensembl, Alliance of Genome Resources - public APIs,
  no credentials, only what the user types is sent.
- **From the server** (`external_lookup`): only `https://www.xenbase.org`
  and `https://rest.rgd.mcw.edu`, port 443, no credentials in the URL -
  checked before each request, so a parameter can't make the server fetch
  anything else. User values go in as URL-encoded query parameters or a
  numeric id. Each page read is bounded (20 s, 8 s per Xenbase line page,
  15 s for all of a gene's lines), and a remote failure returns an empty
  list.
- `update-schema` downloads from `raw.githubusercontent.com/Phen-ICS/fair3r-fdf-schema`
  (30 s timeout). The schema decides which APIs the form calls and which
  regular expressions validate fields: whoever can push to that
  repository's `main` branch changes the form on every server within a day.

## Limits

| What | Limit |
|---|---|
| Account requests | 20 per hour, site-wide (behind the reverse proxy every visitor has the same address, so a per-visitor count would mean nothing) |
| Xenbase line types | 15 s per lookup in total |
| Uploads | CKAN's own `ckan.max_resource_size`; Zenodo uploads have ckanext-zenodo's limits |

## Known limitations

- **FDF checks only apply to the form.** `package_create` /
  `package_update` through the API accept any `fdf_output_json` and
  `datacite.*` extras without validating them (CKAN's own validation
  still applies). They're still escaped when displayed.
- **One web request per lookup or ZIP.** `external_lookup` and "Download
  all" run inside the user's request; with a single web worker, a slow
  one makes the whole site wait. Bounded as above for lookups; the ZIP's
  time grows with the dataset's files.
- **The account request limit is shared**: a bot sending 20 requests in an
  hour blocks real requests until the next hour (they get "try again
  later", nothing is lost silently).
