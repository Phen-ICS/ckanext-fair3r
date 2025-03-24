import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit


class Fair3RPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    

    # IConfigurer

    def update_config(self, config_):

        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "fair3r")

    def get_helpers(self):
        return {
            'get_fair3r_context': self.get_fair3r_context
        }

    def get_fair3r_context(self):
        """Fetch the fair3r context from the configuration"""
        return toolkit.config.get('ckanext.fair3r.context', None)

    
