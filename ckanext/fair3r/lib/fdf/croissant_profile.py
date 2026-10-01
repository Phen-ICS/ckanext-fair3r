"""
Croissant RDF profile extension exposing FAIR3R FDF metadata.

ckanext-dcat's CroissantProfile only reads a fixed set of core CKAN dataset
fields (title, notes, license, creator, publisher, tags, temporal/spatial,
resources...). The FAIR3R Dataset Form (FDF) metadata is stored separately as
package extras (see lib/fdf/extras.py): the raw form output in
"fdf_output_json", plus a DataCite-shaped subset already flattened into
"datacite.*" extras for ckanext-doi. None of that is visible to Croissant by
default.

CroissantProfile.additional_fields() is the extension point ckanext-dcat
documents for exactly this case ("For a custom schema you should extend this
class and implement this method."). See schemaorg_fields.py for the actual
FDF -> schema.org field mapping, shared with schemaorg_profile.py.
"""

from rdflib.namespace import Namespace

from ckanext.dcat.profiles.croissant import CroissantProfile
from ckanext.fair3r.lib.fdf.schemaorg_fields import FDFSchemaOrgFieldsMixin


class Fair3RCroissantProfile(FDFSchemaOrgFieldsMixin, CroissantProfile):
    """CroissantProfile extended with FAIR3R FDF form metadata."""

    # The Croissant validator insists on https (see ckanext-dcat's own
    # croissant.py), unlike the plain schema.org profile.
    SCHEMA = Namespace("https://schema.org/")
