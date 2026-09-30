"""
Plain schema.org RDF profile extension exposing FAIR3R FDF metadata.

ckanext-dcat's "structured_data" plugin embeds this profile's output as its
own <script type="application/ld+json"> block directly on dataset pages -
separately from, and in addition to, the Croissant one. Without this, that
second block still lacked all FDF metadata even after croissant_profile.py
was fixed. See schemaorg_fields.py for the actual FDF -> schema.org field
mapping, shared with croissant_profile.py.
"""

from ckanext.dcat.profiles.base import SCHEMA
from ckanext.dcat.profiles.schemaorg import SchemaOrgProfile
from ckanext.fair3r.lib.fdf.schemaorg_fields import FDFSchemaOrgFieldsMixin


class Fair3RSchemaOrgProfile(FDFSchemaOrgFieldsMixin, SchemaOrgProfile):
    """SchemaOrgProfile extended with FAIR3R FDF form metadata."""

    # ckanext-dcat's own base.py SCHEMA constant is http://schema.org/ (not
    # https) - must match what SchemaOrgProfile itself already emits.
    SCHEMA = SCHEMA
