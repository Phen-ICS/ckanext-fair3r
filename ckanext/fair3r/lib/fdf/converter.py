"""
FDF to CKAN Dataset Converter

Extracts author and maintainer contact info from FAIR3R Dataset Form (FDF) JSON.
Minimal converter focused only on CKAN core contact fields.
"""

import json
import logging
from typing import Any

log = logging.getLogger(__name__)


class FDFConverter:
    """Extract core contact fields (author/maintainer) from FDF data."""

    @staticmethod
    def _person_name(person: dict[str, Any]) -> str:
        if not isinstance(person, dict):
            return ""
        return " ".join(
            filter(
                None,
                [
                    (person.get("givenName") or "").strip(),
                    (person.get("familyName") or "").strip(),
                ],
            )
        ).strip()

    @staticmethod
    def _person_email(person: dict[str, Any]) -> str:
        if not isinstance(person, dict):
            return ""
        return (person.get("email") or "").strip()

    @staticmethod
    def convert_to_ckan_dataset(
        fdf_data: dict[str, Any], user_id: str | None = None
    ) -> dict[str, Any]:
        """
        Extract author and maintainer contact info from FDF form data.

        Role-aware mapping (single-value CKAN fields):
        - first creator with role Author (or no role) -> author
        - first creator with role Maintainer/DataManager -> maintainer

        Args:
            fdf_data: FDF form data dict
            user_id: CKAN user ID (unused but kept for signature compatibility)

        Returns:
            Dict with author, author_email, maintainer, maintainer_email (only populated if present)
        """
        dataset = {}

        # Extract author and maintainer from creators list. The Creator's
        # `role` field (Author/Maintainer) is now stored directly on the
        # creator object. Legacy datasets that derived contributors from
        # creators are still honored via the data_manager_names fallback.
        creators = fdf_data.get("creators", [])
        contributors = fdf_data.get("contributors", [])
        data_manager_names = set()
        if isinstance(contributors, list):
            for contributor in contributors:
                if not isinstance(contributor, dict):
                    continue
                contributor_type = (
                    str(contributor.get("contributorType") or "").strip().lower()
                )
                contributor_name = str(contributor.get("name") or "").strip().lower()
                if contributor_type == "datamanager" and contributor_name:
                    data_manager_names.add(contributor_name)

        role_aware = []
        for creator in creators:
            if not isinstance(creator, dict):
                continue
            name = FDFConverter._person_name(creator)
            email = FDFConverter._person_email(creator)
            if not name and not email:
                continue

            role_raw = (
                str(creator.get("role") or creator.get("contributorType") or "")
                .strip()
                .lower()
            )
            is_maintainer = role_raw in {"maintainer", "datamanager"}
            if not is_maintainer and name:
                is_maintainer = name.lower() in data_manager_names

            role_aware.append(
                {
                    "name": name,
                    "email": email,
                    "is_maintainer": is_maintainer,
                }
            )

        author_candidates = [p for p in role_aware if not p["is_maintainer"]]
        maintainer_candidates = [p for p in role_aware if p["is_maintainer"]]

        first_author = author_candidates[0] if author_candidates else None
        first_maintainer = maintainer_candidates[0] if maintainer_candidates else None

        if first_author:
            if first_author.get("name"):
                dataset["author"] = first_author["name"]
            if first_author.get("email"):
                dataset["author_email"] = first_author["email"]

        if first_maintainer:
            if first_maintainer.get("name"):
                dataset["maintainer"] = first_maintainer["name"]
            if first_maintainer.get("email"):
                dataset["maintainer_email"] = first_maintainer["email"]

        log.info(
            "Extracted contact fields from FDF: author=%s, maintainer=%s",
            dataset.get("author"),
            dataset.get("maintainer"),
        )
        return dataset

    @staticmethod
    def _make_safe_name(title: str) -> str:
        """Convert title to safe dataset name (lowercase alphanumeric with hyphens)."""
        import re

        name = (title or "").lower()
        name = re.sub(r"[\s_]+", "-", name)
        name = re.sub(r"[^a-z0-9-]", "", name)
        name = name.strip("-")[:100]
        return name or "dataset"


def fdf_json_to_ckan_dataset(
    fdf_json_str: str, user_id: str | None = None
) -> dict[str, Any]:
    """
    Extract author/maintainer from FDF JSON string.

    Args:
        fdf_json_str: JSON string from FDF form
        user_id: CKAN user ID (unused, kept for compatibility)

    Returns:
        Dict with author, author_email, maintainer, maintainer_email (if present)
    """
    try:
        fdf_data = json.loads(fdf_json_str)
    except (TypeError, ValueError) as e:
        log.error("Failed to parse FDF JSON: %s", e)
        raise ValueError(f"Invalid FDF JSON: {e}")

    return FDFConverter.convert_to_ckan_dataset(fdf_data, user_id)
