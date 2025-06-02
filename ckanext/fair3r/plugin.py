import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import ckan.lib.mailer as ckan_mailer
from ckanext.fair3r.lib import mailer as fair3r_mailer


class Fair3RPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)


    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "fair3r")

        # Override CKAN mailer functions with our custom ones
        self._override_mailer_functions()

    def get_helpers(self):
        return {
            'get_fair3r_context': self.get_fair3r_context
        }

    def get_fair3r_context(self):
        """Fetch the fair3r context from the configuration"""
        return toolkit.config.get('ckanext.fair3r.context', None)

    def _override_mailer_functions(self):
        """
        Override CKAN mailer functions with our custom ones to support HTML emails.
        """
        ckan_mailer.send_reset_link = fair3r_mailer.send_reset_link
        ckan_mailer.send_invite = fair3r_mailer.send_invite
