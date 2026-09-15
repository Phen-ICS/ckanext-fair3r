from setuptools import setup

setup(
    # If you are changing from the default layout of your extension, you may
    # have to change the message extractors, you can read more about babel
    # message extraction at
    # http://babel.pocoo.org/docs/messages/#extraction-method-mapping-and-configuration
    message_extractors={
        "ckanext": [
            ("**.py", "python", None),
            # parse_template_string is needed to extract _() calls embedded
            # in JS template literals (`...${_("msg")}...`).
            ("**.js", "javascript", {"parse_template_string": "true"}),
            ("**/templates/**.html", "ckan", None),
        ],
    },
    entry_points="""
        [ckan.plugins]
        fair3r=ckanext.fair3r.plugin:Fair3RPlugin
    """,
    install_requires=[
        "cryptography==46.0.3",
    ],
    package_data={
        "ckanext.fair3r.tests": ["test.ini"],
    },
    version="3.1.13",
)
