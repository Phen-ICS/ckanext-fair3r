# Blueprints package for ckanext-fair3r

from ckanext.fair3r.blueprints.download_all import download_all
from ckanext.fair3r.blueprints.activity_guard import activity_guard
from ckanext.fair3r.blueprints.account_request import account_request
from ckanext.fair3r.blueprints.dataset_choice import dataset_choice
from ckanext.fair3r.blueprints.fdf import fdf
from ckanext.fair3r.blueprints.sitemap import sitemap

__all__ = [
    "download_all",
    "activity_guard",
    "account_request",
    "dataset_choice",
    "fdf",
    "sitemap",
]
