import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import ckan.lib.mailer as ckan_mailer
from ckanext.fair3r.lib import mailer as fair3r_mailer
from ckanext.fair3r.blueprints.fco_integration import fco_integration
from ckanext.fair3r.blueprints.download_all import download_all_bp
from ckanext.fair3r.blueprints.activity_guard import activity_guard_bp
from ckanext.fair3r.blueprints.account_request import account_request_bp


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
            'get_fair3r_context': self.get_fair3r_context,
            'is_superadmin': self.is_superadmin
        }

    def get_fair3r_context(self):
        """Fetch the fair3r context from the configuration"""
        return toolkit.config.get('ckanext.fair3r.context', None)

    def is_superadmin(self):
        """Check if the current user is a superadmin"""
        if not toolkit.c.user:
            return False
        
        from ckan.model import User
        user = User.get(toolkit.c.user)
        return user and user.sysadmin

    def _override_mailer_functions(self):
        """
        Override CKAN mailer functions with our custom ones to support HTML emails.
        """
        ckan_mailer.send_reset_link = fair3r_mailer.send_reset_link
        ckan_mailer.send_invite = fair3r_mailer.send_invite

    # IBlueprint

    def get_blueprint(self):
        """Register extension blueprints (FCO integration, download-all, guards)."""
        return [fco_integration, download_all_bp, activity_guard_bp, account_request_bp]
