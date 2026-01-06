"""
Sitemap Blueprint

This blueprint generates a sitemap.xml for better SEO and search engine indexing.
The sitemap includes home page, create dataset page, organizations, and datasets.
"""

import logging
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from flask import Blueprint, Response
import ckan.plugins.toolkit as toolkit

log = logging.getLogger(__name__)

sitemap = Blueprint('sitemap', __name__)


@sitemap.route('/sitemap.xml')
def sitemap_xml():
    """
    Generate and return sitemap.xml.
    
    The sitemap includes:
    - Home page
    - Create dataset page
    - Organizations list
    - Individual organization pages
    - Datasets list
    - Individual dataset pages
    """
    try:
        # Get site URL from configuration
        site_url = toolkit.config.get('ckan.site_url', '').rstrip('/')
        if not site_url:
            log.warning("ckan.site_url not configured, sitemap may have incorrect URLs")
            site_url = 'http://localhost:5000'
        
        # Create root element
        urlset = Element('urlset')
        urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        
        # Context for API calls (no authentication needed for public data)
        context = {'ignore_auth': True}
        
        # 1. Home page
        url_elem = SubElement(urlset, 'url')
        SubElement(url_elem, 'loc').text = f"{site_url}/"
        SubElement(url_elem, 'changefreq').text = 'daily'
        SubElement(url_elem, 'priority').text = '1.0'
        
        # 2. Create dataset page
        url_elem = SubElement(urlset, 'url')
        SubElement(url_elem, 'loc').text = f"{site_url}/dataset/new"
        SubElement(url_elem, 'changefreq').text = 'monthly'
        SubElement(url_elem, 'priority').text = '0.8'
        
        # 3. Organizations list page
        url_elem = SubElement(urlset, 'url')
        SubElement(url_elem, 'loc').text = f"{site_url}/organization"
        SubElement(url_elem, 'changefreq').text = 'weekly'
        SubElement(url_elem, 'priority').text = '0.9'
        
        # 4. Datasets list page
        url_elem = SubElement(urlset, 'url')
        SubElement(url_elem, 'loc').text = f"{site_url}/dataset"
        SubElement(url_elem, 'changefreq').text = 'daily'
        SubElement(url_elem, 'priority').text = '0.9'
        
        # 5. Get and add all organizations
        try:
            orgs = toolkit.get_action('organization_list')(context, {
                'all_fields': True,
                'include_dataset_count': False
            })
            
            for org in orgs:
                org_name = org.get('name', '')
                if org_name:
                    url_elem = SubElement(urlset, 'url')
                    SubElement(url_elem, 'loc').text = f"{site_url}/organization/{org_name}"
                    SubElement(url_elem, 'changefreq').text = 'weekly'
                    SubElement(url_elem, 'priority').text = '0.7'
                    
        except Exception as e:
            log.warning(f"Error fetching organizations for sitemap: {e}")
        
        # 6. Get and add all datasets
        try:
            # Get list of all public datasets
            datasets = toolkit.get_action('package_list')(context, {})
            
            for dataset_name in datasets:
                if dataset_name:
                    url_elem = SubElement(urlset, 'url')
                    SubElement(url_elem, 'loc').text = f"{site_url}/dataset/{dataset_name}"
                    SubElement(url_elem, 'changefreq').text = 'weekly'
                    SubElement(url_elem, 'priority').text = '0.6'
                    
        except Exception as e:
            log.warning(f"Error fetching datasets for sitemap: {e}")
        
        # Convert to pretty XML string
        rough_string = tostring(urlset, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
        
        # Return XML response
        return Response(
            pretty_xml,
            mimetype='application/xml',
            headers={'Content-Type': 'application/xml; charset=utf-8'}
        )
        
    except Exception as e:
        log.error(f"Error generating sitemap: {e}")
        # Return minimal sitemap on error
        site_url = toolkit.config.get('ckan.site_url', 'http://localhost:5000').rstrip('/')
        urlset = Element('urlset')
        urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        url_elem = SubElement(urlset, 'url')
        SubElement(url_elem, 'loc').text = f"{site_url}/"
        
        rough_string = tostring(urlset, encoding='utf-8')
        return Response(
            rough_string,
            mimetype='application/xml',
            headers={'Content-Type': 'application/xml; charset=utf-8'}
        )
