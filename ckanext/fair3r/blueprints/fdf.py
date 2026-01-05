"""
FDF (Fair3R Dataset Form) Blueprint

This blueprint handles the FDF dataset creation form, which is part of ckanext-fair3r.
"""

import logging

from flask import Blueprint, redirect
import ckan.plugins.toolkit as toolkit
from ckanext.fair3r.lib.decorators import login_required
from ckanext.fair3r.lib.utils import asbool

log = logging.getLogger(__name__)

fdf = Blueprint('fdf', __name__)


@fdf.route('/dataset/new/fdf')
@login_required(redirect_to='user.login')
def fdf_dataset_creation():
    """
    FDF (Fair3R Dataset Form) dataset creation.
    
    This route provides access to the Fair3R Dataset Form interface for
    dataset creation. This is part of ckanext-fair3r.
    """
    enable_fdf = asbool(toolkit.config.get('ckanext.fair3r.enable_fdf_integration', False))
    
    # If FDF integration is disabled, fall back to standard CKAN form
    if not enable_fdf:
        return redirect(toolkit.url_for('fco_integration.ckan_dataset_creation'))
    
    # Render the FDF template
    return toolkit.render('package/fdf_form.html', {
        'pkg_dict': None,
        'dataset_type': 'dataset'
    })
