## How to add a new blueprint that (if) renders an overridden CKAN template

Goal
- Expose a custom route, run some logic, and render a template that we override inside this extension.

Steps
- Define the blueprint in a module (e.g., `ckanext/fair3r/blueprints/custom.py`) using Flask’s `Blueprint`.
- Register routes on the blueprint.
- Return a rendered template via `toolkit.render('path/to/template.html', extra_vars)`; the path must match the overridden template name under our `templates/`.
- Implement `IBlueprint` in `plugin.py`, returning the blueprint object from `get_blueprint()` (or `get_blueprints()` on CKAN ≥2.10).
- Add any needed assets (CSS/JS) under `public/` and load them from the template using CKAN’s asset helpers if required.

Example skeleton
- `ckanext/fair3r/blueprints/custom.py`
  - Create blueprint: `bp = Blueprint('fair3r_custom', __name__)`
  - Route: `@bp.route('/fair3r/custom')`
  - Handler:
    - Fetch/process domain data.
    - Return `toolkit.render('fair3r/custom.html', extra_vars={'data': data})`.
- `plugin.py`
  - `class Fair3RPlugin(plugins.SingletonPlugin):`
  - `plugins.implements(plugins.IBlueprint)`; `def get_blueprint(self): return bp`.

Template override linkage
- Place the target template under `ckanext/fair3r/templates/fair3r/custom.html`.
- Ensure `update_config` (via `IConfigurer`) adds our templates path: `toolkit.add_template_directory(config, 'templates')`.
- If overriding a core CKAN template, mirror its relative path (e.g., `templates/package/read.html`).
