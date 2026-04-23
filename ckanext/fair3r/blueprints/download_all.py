from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from typing import Any, cast

from flask import Blueprint, send_file, after_this_request

import ckan.lib.base as base
import ckan.lib.uploader as uploader
import ckan.logic as logic
import ckan.model as model
from ckan.common import _, current_user
from ckan.types import Context


download_all = Blueprint(
    "download_all",
    __name__,
    url_prefix="/dataset",
)
log = logging.getLogger(__name__)


def _safe_arcname(filename: str, fallback: str) -> str:
    name = (filename or "").strip().replace("\\", "/")
    base_name = os.path.basename(name)
    if not base_name:
        base_name = fallback
    # Avoid directory traversal or absolute paths
    base_name = base_name.replace("/", "_")
    return base_name


@download_all.route("/<id>/download-all", methods=["GET"])
def download(id: str):
    context = cast(
        Context,
        {
            "model": model,
            "session": model.Session,
            "user": current_user.name,
            "auth_user_obj": current_user,
            "for_view": True,
        },
    )

    get_action = logic.get_action
    NotFound = logic.NotFound
    NotAuthorized = logic.NotAuthorized

    try:
        package = get_action("package_show")(context, {"id": id})
    except NotFound:
        return base.abort(404, _("Dataset not found"))
    except NotAuthorized:
        return base.abort(403, _("Not authorized to access dataset"))

    resources: list[dict[str, Any]] = package.get("resources", [])

    uploaded_resources = [r for r in resources if r.get("url_type") == "upload"]

    if not uploaded_resources:
        return base.abort(404, _("No uploaded resources available to download"))

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_file_path = temp_file.name
    temp_file.close()

    def _format_dataset_metadata_text(pkg: dict[str, Any]) -> str:
        lines: list[str] = []
        lines.append("Dataset metadata")
        lines.append("=================")
        lines.append("")

        def add(k: str, v: Any):
            if v is None:
                v = ""
            lines.append(f"{k}: {v}")

        add("ID", pkg.get("id"))
        add("Name", pkg.get("name"))
        add("Title", pkg.get("title"))
        add("Notes", pkg.get("notes"))
        add("Author", pkg.get("author"))
        add("Author Email", pkg.get("author_email"))
        add("Maintainer", pkg.get("maintainer"))
        add("Maintainer Email", pkg.get("maintainer_email"))
        add("License", pkg.get("license_title") or pkg.get("license_id"))
        add("Owner Org", pkg.get("owner_org"))
        add("Private", pkg.get("private"))
        add("Created", pkg.get("metadata_created"))
        add("Last Modified", pkg.get("metadata_modified"))
        add("State", pkg.get("state"))
        add("Type", pkg.get("type"))

        # Organization
        org = pkg.get("organization") or {}
        if isinstance(org, dict) and org.get("name"):
            lines.append("")
            lines.append("Organization")
            lines.append("------------")
            add("Org ID", org.get("id"))
            add("Org Name", org.get("name"))
            add("Org Title", org.get("title"))

        # Tags
        tags = pkg.get("tags") or []
        if tags:
            lines.append("")
            lines.append("Tags")
            lines.append("----")
            for t in tags:
                if isinstance(t, dict):
                    lines.append(f"- {t.get('name')}")
                else:
                    lines.append(f"- {t}")

        # Groups
        groups = pkg.get("groups") or []
        if groups:
            lines.append("")
            lines.append("Groups")
            lines.append("------")
            for g in groups:
                if isinstance(g, dict):
                    lines.append(f"- {g.get('name')} ({g.get('title')})")

        # Extras
        extras = pkg.get("extras") or []
        if extras:
            lines.append("")
            lines.append("Extras")
            lines.append("------")
            if isinstance(extras, list):
                for e in extras:
                    if isinstance(e, dict):
                        lines.append(f"- {e.get('key')}: {e.get('value')}")
            elif isinstance(extras, dict):
                for k, v in extras.items():
                    lines.append(f"- {k}: {v}")

        # Resources list
        lines.append("")
        lines.append("Resources")
        lines.append("---------")
        for r in pkg.get("resources", []) or []:
            name = r.get("name") or r.get("id")
            desc = r.get("description") or ""
            fmt = r.get("format") or r.get("mimetype") or ""
            url = r.get("url") or ""
            included = "upload" if r.get("url_type") == "upload" else "link"
            lines.append(f"- {name}")
            if desc:
                lines.append(f"  Description: {desc}")
            if fmt:
                lines.append(f"  Format: {fmt}")
            if url:
                lines.append(f"  URL: {url}")
            lines.append(f"  Type: {included}")

        lines.append("")
        return "\n".join(lines)

    try:
        with zipfile.ZipFile(
            temp_file_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as zf:
            # Add dataset metadata summary file
            metadata_text = _format_dataset_metadata_text(package)
            dataset_name = package.get("name") or package.get("id") or "dataset"
            meta_filename = _safe_arcname(
                f"{dataset_name}-metadata.txt", "metadata.txt"
            )
            zf.writestr(meta_filename, metadata_text)

            for res in uploaded_resources:
                res_id = res.get("id")
                if not res_id:
                    continue

                try:
                    upload = uploader.get_resource_uploader(res)
                    file_path = upload.get_path(res_id)
                except Exception as e:
                    log.warning("Skipping resource %s in archive build: %s", res_id, e)
                    file_path = None

                if not file_path or not os.path.exists(file_path):
                    continue

                # Try to build a friendly filename
                url = res.get("url", "") or ""
                # In CKAN uploaded resources, the URL often ends with /download/<filename>
                candidate_filename = ""
                if "/download/" in url:
                    candidate_filename = url.split("/download/")[-1]
                arcname = _safe_arcname(
                    candidate_filename,
                    f"{res.get('name') or 'resource'}-{res_id}{os.path.splitext(file_path)[1]}",
                )

                zf.write(file_path, arcname=arcname)

        response = send_file(
            temp_file_path,
            as_attachment=True,
            download_name=f"{package.get('name') or package.get('id')}.zip",
            mimetype="application/zip",
            conditional=True,
        )

        @after_this_request
        def cleanup_temp_file(response_obj):  # type: ignore[no-redef]
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
            return response_obj

        return response
    except Exception:
        try:
            os.remove(temp_file_path)
        except OSError:
            pass
        return base.abort(500, _("Failed to build ZIP archive"))
