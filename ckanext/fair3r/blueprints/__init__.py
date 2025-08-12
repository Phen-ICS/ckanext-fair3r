# Blueprints package for ckanext-fair3r

from ckanext.fair3r.blueprints.fco_integration import fco_integration  # noqa: F401
from ckanext.fair3r.blueprints.download_all import download_all_bp  # noqa: F401

__all__ = [
    "fco_integration",
    "download_all_bp",
]