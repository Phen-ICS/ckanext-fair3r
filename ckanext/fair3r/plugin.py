import ckan.plugins as plugins
from logging import getLogger
import ckan.plugins.toolkit as toolkit  # module containing toolkit functions, classes and exceptions for use by CKAN extensions.
import ckan.lib.mailer as ckan_mailer
from ckan.common import current_user, request
from ckanext.fair3r.lib import mailer as fair3r_mailer
from ckanext.fair3r.blueprints.fco_integration import fco_integration
from ckanext.fair3r.blueprints.download_all import download_all
from ckanext.fair3r.blueprints.activity_guard import activity_guard
from ckanext.fair3r.blueprints.account_request import account_request
from ckanext.fair3r.blueprints.dataset_choice import dataset_choice
from ckanext.fair3r.blueprints.fdf import fdf
from ckanext.fair3r.blueprints.sitemap import sitemap

# Routing: register blueprints (`IBlueprint`) to expose custom endpoints.
# Templating/theming: add template/public asset paths (`IConfigurer`) for overrides.
# Authz/action overrides: expose `get_auth_functions` (`IAuthFunctions`) or `get_actions`.
# CLI/admin hooks: register custom commands (`IClick`).
# Validation and schema: implement `IDatasetForm` or `IValidators`.

log = getLogger(__name__)


class Fair3RPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IBlueprint)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "fair3r")

        # Override CKAN mailer functions with our custom ones
        self._override_mailer_functions()

    def get_helpers(self):
        return {
            "fair3r_current_user": self.fair3r_current_user,
            "fair3r_is_authenticated": self.fair3r_is_authenticated,
            "fair3r_is_resource_read": self.fair3r_is_resource_read,
            "fair3r_context": self.fair3r_context,
            "fair3r_is_superadmin": self.fair3r_is_superadmin,
        }

    def fair3r_context(self):
        """Fetch the fair3r context from the configuration"""
        return toolkit.config.get("ckanext.fair3r.context", None)

    def fair3r_is_superadmin(self):
        """Check if the current user is a superadmin"""
        if getattr(current_user, "is_anonymous", True):
            return False
        return bool(getattr(current_user, "sysadmin", False))

    def fair3r_current_user(self):
        """Return the current user object (or anonymous user) for templates."""
        return current_user

    def fair3r_is_authenticated(self):
        """Check if the current user is authenticated."""
        return not getattr(current_user, "is_anonymous", True)

    def fair3r_is_resource_read(self):
        """Check if the current endpoint is a resource read page."""
        endpoint = request.endpoint or ""
        return endpoint.endswith("resource.read") or endpoint.endswith("_resource.read")

    def _override_mailer_functions(self):
        """
        Override CKAN mailer functions with our custom ones to support HTML emails.
        """
        ckan_mailer.send_reset_link = fair3r_mailer.send_reset_link
        ckan_mailer.send_invite = fair3r_mailer.send_invite

    # IBlueprint

    def get_blueprint(self):
        """Register extension blueprints (FCO integration, download-all, guards, account request, dataset creation, FDF, sitemap)."""
        return [
            fco_integration,
            download_all,
            activity_guard,
            account_request,
            dataset_choice,
            fdf,
            sitemap,
        ]
