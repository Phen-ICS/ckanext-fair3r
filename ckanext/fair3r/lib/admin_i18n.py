"""Sysadmin page strings for Babel extraction (CKAN core fr catalog gap)."""

from ckan.plugins import toolkit


def admin_page_msgids():
    """Register sysadmin page msgids for extract_messages."""
    return (
        toolkit._("Administer CKAN"),
        toolkit._("Current Sysadmins"),
        toolkit._("Promote"),
        toolkit._("Promote user to Sysadmin"),
        toolkit._("Revoke Sysadmin permission"),
        toolkit._("About page text"),
        toolkit._("Are you sure you want to reset the config?"),
        toolkit._("CKAN config options"),
        toolkit._("Custom CSS"),
        toolkit._("Custom Stylesheet"),
        toolkit._("Customisable css inserted into the page header"),
        toolkit._("Intro Text"),
        toolkit._("Reset"),
        toolkit._("Site Tag Line"),
        toolkit._("Site Title"),
        toolkit._("Site logo"),
        toolkit._("Text on home page"),
        toolkit._("Update Config"),
        toolkit._("Are you sure you want to purge everything?"),
        toolkit._("Are you sure you want to purge datasets?"),
        toolkit._("Are you sure you want to purge groups?"),
        toolkit._("Are you sure you want to purge organizations?"),
        toolkit._("Deleted datasets"),
        toolkit._("Deleted groups"),
        toolkit._("Deleted organizations"),
        toolkit._("Massive purge complete"),
        toolkit._("Purge"),
        toolkit._("Purge all"),
        toolkit._("There are no datasets to purge"),
        toolkit._("There are no groups to purge"),
        toolkit._("There are no organizations to purge"),
        toolkit._("Trash"),
        toolkit._("{number} datasets have been purged"),
        toolkit._("{number} groups have been purged"),
        toolkit._("{number} organizations have been purged"),
    )
