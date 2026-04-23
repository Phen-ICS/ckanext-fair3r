"""
Sitemap Blueprint

This blueprint generates a sitemap.xml for better SEO and search engine indexing.
The sitemap includes home page, create dataset page, organizations, and datasets.
"""

import logging
from html import escape

from flask import Blueprint, Response
import ckan.plugins.toolkit as toolkit

log = logging.getLogger(__name__)

sitemap = Blueprint("sitemap", __name__)


def _render_sitemap_xml(entries: list[tuple[str, str, str]]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, changefreq, priority in entries:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{escape(loc)}</loc>",
                f"    <changefreq>{escape(changefreq)}</changefreq>",
                f"    <priority>{escape(priority)}</priority>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    return "\n".join(lines)


@sitemap.route("/sitemap.xml")
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
        site_url = toolkit.config.get("ckan.site_url", "").rstrip("/")
        if not site_url:
            log.warning("ckan.site_url not configured, sitemap may have incorrect URLs")
            site_url = "http://localhost:5000"

        entries: list[tuple[str, str, str]] = []

        # Context for API calls (no authentication needed for public data)
        context = {"ignore_auth": True}

        # 1. Home page
        entries.append((f"{site_url}/", "daily", "1.0"))

        # 2. Create dataset page
        entries.append((f"{site_url}/dataset/new", "monthly", "0.8"))

        # 3. Organizations list page
        entries.append((f"{site_url}/organization", "weekly", "0.9"))

        # 4. Datasets list page
        entries.append((f"{site_url}/dataset", "daily", "0.9"))

        # 5. Get and add all organizations
        try:
            orgs = toolkit.get_action("organization_list")(
                context, {"all_fields": True, "include_dataset_count": False}
            )

            for org in orgs:
                org_name = org.get("name", "")
                if org_name:
                    entries.append(
                        (f"{site_url}/organization/{org_name}", "weekly", "0.7")
                    )

        except Exception as e:
            log.warning(f"Error fetching organizations for sitemap: {e}")

        # 6. Get and add all datasets
        try:
            # Get list of all public datasets
            datasets = toolkit.get_action("package_list")(context, {})

            for dataset_name in datasets:
                if dataset_name:
                    entries.append(
                        (f"{site_url}/dataset/{dataset_name}", "weekly", "0.6")
                    )

        except Exception as e:
            log.warning(f"Error fetching datasets for sitemap: {e}")

        xml = _render_sitemap_xml(entries)

        # Return XML response
        return Response(
            xml,
            mimetype="application/xml",
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )

    except Exception as e:
        log.error(f"Error generating sitemap: {e}")
        # Return minimal sitemap on error
        site_url = toolkit.config.get("ckan.site_url", "http://localhost:5000").rstrip(
            "/"
        )
        xml = _render_sitemap_xml([(f"{site_url}/", "daily", "1.0")])
        return Response(
            xml,
            mimetype="application/xml",
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
