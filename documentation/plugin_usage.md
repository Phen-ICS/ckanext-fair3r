## Technical notes: `plugin.py` in a CKAN extension

Overview
- `ckanext/fair3r/plugin.py` defines the extension’s plugins; CKAN discovers them via `entry_points` in `setup.py` and loads them when listed in `ckan.plugins`.
- Classes should inherit `ckan.plugins.SingletonPlugin` and declare implemented interfaces (e.g., `IBlueprint`, `IConfigurer`, `IAuthFunctions`) with `plugins.implements(...)`.
- Each implemented method is invoked by CKAN’s plugin toolkit at defined lifecycle points.

Typical lifecycle
- Add the plugin class path to `setup.py` under `[ckan.plugins]`.
- Install in the CKAN virtualenv
- Enable via `ckan.plugins = ... fair3r` (use the left-hand side name from `setup.py`).
- Restart CKAN to pick up changes.

Common responsibilities in `plugin.py`
- Routing: register blueprints (`IBlueprint`) to expose custom endpoints.
- Templating/theming: add template/public asset paths (`IConfigurer`) for overrides.
- Authz/action overrides: expose `get_auth_functions` (`IAuthFunctions`) or `get_actions`.
- CLI/admin hooks: register custom commands (`IClick`).
- Validation and schema: implement `IDatasetForm` or `IValidators`.

References
- CKAN extension tutorial: https://docs.ckan.org/en/2.10/extensions/tutorial.html#creating-a-new-extension
- Plugin class basics: https://docs.ckan.org/en/2.10/extensions/tutorial.html#creating-a-plugin-class
