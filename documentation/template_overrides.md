## How to find CKAN templates and override them in `ckanext-fair3r`

Finding the source template
- Core templates live in `ckan/templates/` (inside the CKAN source). Common subpaths: `package/`, `group/`, `organization/`, `home/`, `snippets/`.
- Search by filename (e.g., `read.html`, `edit.html`, `layout1.html`) to confirm the relative path.
- Inspect the template for required variables and included snippets so our override provides the same inputs.

Creating the override
- Mirror the relative path under this extension: `ckanext/fair3r/templates/<same relative path>`.
  - Example: to override `ckan/templates/package/read.html`, create `ckanext/fair3r/templates/package/read.html`.
- Register the templates directory in `plugin.py` via `IConfigurer.update_config`: `toolkit.add_template_directory(config, 'templates')`.
- Keep overrides minimal: extend the original where possible using `{% ckan_extends %}` and override only blocks that need changes.
- For assets, place files under `public/` and register with `toolkit.add_public_directory(config, 'public')`; reference them via CKAN’s asset helpers.

Verifying the override is used
- Load the relevant page and confirm changes appear; if not, clear template cache (restart) and check that the relative path matches exactly.
- Use the browser dev tools (eg. FDT) to confirm the template output and asset URLs are correct.

Tips
- Prefer snippet-level overrides over whole-page overrides to reduce drift when upgrading CKAN.
- When adding blocks, preserve original `block` names and context variables.
