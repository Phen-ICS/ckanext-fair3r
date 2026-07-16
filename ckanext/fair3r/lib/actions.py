"""
Custom CKAN actions for ckanext-fair3r.

These are registered via IActions in plugin.py and exposed automatically
at /api/3/action/<name> — no blueprint or Nginx changes required.
"""

import json
import logging
import re
from http.client import HTTPSConnection
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit

import ckan.plugins.toolkit as toolkit

log = logging.getLogger(__name__)


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_ALLOWED_FETCH_HOSTS = frozenset({"www.xenbase.org", "rest.rgd.mcw.edu"})


def _read_remote_text(url, timeout=20, allowed_hosts=None):
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    expected_hosts = allowed_hosts or _ALLOWED_FETCH_HOSTS

    if parsed.scheme != "https":
        raise URLError(f"Unsupported URL scheme: {parsed.scheme!r}")
    if not hostname or hostname not in expected_hosts:
        raise URLError(f"Unexpected remote host: {hostname!r}")
    if parsed.username or parsed.password:
        raise URLError("Credentials in remote URLs are not allowed")
    if parsed.port not in (None, 443):
        raise URLError(f"Unexpected remote port: {parsed.port!r}")

    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    connection = HTTPSConnection(hostname, port=parsed.port or 443, timeout=timeout)
    try:
        connection.request(
            "GET",
            path,
            headers={"Accept": "application/json,text/html;q=0.9,*/*;q=0.8"},
        )
        response = connection.getresponse()
        payload = response.read()
        if response.status >= 400:
            raise HTTPError(
                url, response.status, response.reason, response.headers, None
            )
        return payload.decode("utf-8", "ignore")
    except OSError as exc:
        raise URLError(str(exc)) from exc
    finally:
        connection.close()


def _clean_text(value):
    if not isinstance(value, str):
        return value
    return _HTML_TAG_RE.sub("", unescape(value)).strip()


def _html_to_text(value):
    if not isinstance(value, str):
        return ""
    text = re.sub(
        r"<script\b[^>]*>.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(
        r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_labeled_value(text, label, next_labels=None):
    if not text or not label:
        return ""

    start = text.find(label)
    if start < 0:
        return ""

    value_start = start + len(label)
    remaining = text[value_start:]
    end = len(remaining)

    for next_label in next_labels or []:
        idx = remaining.find(next_label)
        if idx >= 0 and idx < end:
            end = idx

    return remaining[:end].strip(" :-|\t\n\r")


def _fetch_xenbase_line_metadata(line_id, cache=None):
    if not line_id:
        return {}

    cache_key = str(line_id)
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    url = (
        "https://www.xenbase.org/xenbase/stockCenter/showLine.do?method=displayLine&lineId="
        + str(line_id)
    )
    try:
        html = _read_remote_text(url, timeout=20)
    except (HTTPError, URLError):
        metadata = {}
        if cache is not None:
            cache[cache_key] = metadata
        return metadata

    text = _html_to_text(html)
    line_type = _extract_labeled_value(
        text,
        "Line Type:",
        [
            "Mutated Gene(s):",
            "MTA Required:",
            "Public:",
            "Anatomical Phenotypes:",
            "Disease Phenotypes:",
            "Stock Center",
        ],
    )

    metadata = {}
    if line_type:
        metadata["line_type"] = line_type

    if cache is not None:
        cache[cache_key] = metadata
    return metadata


def _enrich_xenbase_lines(items):
    if not isinstance(items, list):
        return items

    metadata_cache = {}
    for item in items:
        if not isinstance(item, dict):
            continue

        line_id = item.get("lineId")
        if not line_id:
            continue

        metadata = _fetch_xenbase_line_metadata(line_id, cache=metadata_cache)
        if metadata.get("line_type"):
            item["line_type"] = metadata["line_type"]

    return items


def _fetch_stockcenter_lines(search_value, search_species=11):
    """Fetch stock-center lines from Xenbase search HTML and parse line entries."""
    if not search_value:
        return []

    params = {
        "method": "searchLines",
        "searchIn": "1",
        "searchValue": search_value,
        "searchSpecies": str(search_species),
        "orderBy": "CREATE_DATE",
        "orderDirection": "DESC",
    }
    url = "https://www.xenbase.org/xenbase/stockCenter/searchLines.do?" + urlencode(
        params
    )

    try:
        html = _read_remote_text(url, timeout=20)
    except (HTTPError, URLError):
        return []

    pattern = re.compile(
        r"showLine\.do[^\"]*?lineId=(\d+)[^\"]*\"[^>]*>(.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )
    seen = set()
    lines = []

    for line_id, anchor_html in pattern.findall(html):
        if line_id in seen:
            continue
        seen.add(line_id)
        name = _clean_text(anchor_html)
        lines.append(
            {
                "lineId": line_id,
                "name": name,
                "display": name,
                "name_clean": name,
                "display_clean": name,
                "url": f"stockCenter/showLine.do?method=displayLine&lineId={line_id}",
                "source": "stockCenter_search",
            }
        )

    return lines


def _xenbase_gene_lines(data_dict):
    gene_id = toolkit.get_or_bust(data_dict, "geneId")
    gene_id = str(gene_id).strip()
    if not gene_id:
        raise toolkit.ValidationError({"geneId": [toolkit._("geneId is required")]})

    # Xenbase geneAjax.do uses an internal numeric ID that is one less than the
    # public accession number in XB-GENE-XXXXXX. Strip the prefix and subtract 1.
    raw_gene_id = re.sub(
        r"^(?:XB-GENE-|Xenbase:XB-GENE-|xenbase:)",
        "",
        gene_id,
        flags=re.IGNORECASE,
    )
    try:
        internal_id = str(int(raw_gene_id) - 1)
    except ValueError:
        internal_id = raw_gene_id

    org_id = str(data_dict.get("orgId") or "trop").strip() or "trop"
    search_species = str(data_dict.get("searchSpecies") or "11").strip() or "11"

    xenbase_params = {
        "method": "jsonifyGene",
        "geneId": internal_id,
        "orgId": org_id,
    }
    xenbase_url = "https://www.xenbase.org/xenbase/gene/geneAjax.do?" + urlencode(
        xenbase_params
    )

    try:
        payload = json.loads(_read_remote_text(xenbase_url, timeout=20))
    except (HTTPError, URLError, ValueError, json.JSONDecodeError) as exc:
        log.warning("Xenbase request failed for geneId=%s: %s", gene_id, exc)
        return {"items": []}

    items = payload.get("mutants", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []

    for item in items:
        for field in ("name", "display"):
            if field in item and isinstance(item[field], str):
                item[field + "_clean"] = _clean_text(item[field])

    if not items and isinstance(payload, dict):
        search_value = payload.get("symbol") or payload.get("gene_symbol")
        items = _fetch_stockcenter_lines(search_value, search_species=search_species)

    items = _enrich_xenbase_lines(items)

    return {"items": items}


def _rgd_gene_variants(data_dict):
    gene_id = toolkit.get_or_bust(data_dict, "geneId")
    gene_id = str(gene_id).strip()
    if not gene_id:
        raise toolkit.ValidationError({"geneId": [toolkit._("geneId is required")]})

    # Accept values like "RGD:620474" or "620474" and keep numeric token.
    match = re.search(r"(\d+)$", gene_id)
    if not match:
        raise toolkit.ValidationError(
            {"geneId": [toolkit._("geneId must contain a numeric RGD identifier")]}
        )
    rgd_gene_id = match.group(1)

    requested_map_key = str(data_dict.get("mapKey") or "380").strip() or "380"
    fallback_map_keys = [requested_map_key, "372", "380", "360", "70"]
    map_keys = []
    for mk in fallback_map_keys:
        if mk and mk not in map_keys:
            map_keys.append(mk)

    items = []
    for map_key in map_keys:
        url = f"https://rest.rgd.mcw.edu/rgdws/variants/gene/{rgd_gene_id}/{map_key}"
        try:
            payload = json.loads(_read_remote_text(url, timeout=20))
            current = payload if isinstance(payload, list) else []
            if current:
                items = current
                break
        except (HTTPError, URLError, ValueError, json.JSONDecodeError) as exc:
            log.warning(
                "RGD variants request failed for geneId=%s mapKey=%s: %s",
                rgd_gene_id,
                map_key,
                exc,
            )

    normalized = []
    seen_ids = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        rs_id = str(item.get("rsId") or "").strip()
        variant_type = str(item.get("variantType") or "").strip()
        chromosome = str(item.get("chromosome") or "").strip()
        start_pos = item.get("startPos")
        end_pos = item.get("endPos")

        if rs_id:
            label = rs_id
            value_uri = f"https://identifiers.org/dbsnp:{rs_id}"
        elif chromosome and start_pos:
            label = f"{chromosome}:{start_pos}"
            value_uri = f"https://rgd.mcw.edu/rgdweb/search/search.html?term={label}"
        else:
            continue

        if value_uri in seen_ids:
            continue
        seen_ids.add(value_uri)

        normalized.append(
            {
                "label": label,
                "display": label,
                "id": value_uri,
                "value_uri": value_uri,
                "variantType": variant_type,
                "sublabel": variant_type,
                "chromosome": chromosome,
                "startPos": start_pos,
                "endPos": end_pos,
                "referenceNucleotide": item.get("referenceNucleotide"),
                "variantNucleotide": item.get("variantNucleotide"),
                "rsId": rs_id,
                "source": "RGD",
            }
        )

    return {"items": normalized}


@toolkit.side_effect_free
def external_lookup(context, data_dict):
    """Generic server-side lookup endpoint driven by schema parameters.

    Example:
    GET /api/3/action/external_lookup?provider=xenbase&resource=gene_lines&geneId=XB-GENE-484088
    """
    if not context.get("user") and not context.get("auth_user_obj"):
        raise toolkit.NotAuthorized(toolkit._("Authentication required"))

    provider = str(data_dict.get("provider") or "").strip().lower()
    resource = str(data_dict.get("resource") or "").strip().lower()

    if provider == "xenbase" and resource in {"gene_lines", "gene_mutants", "strains"}:
        return _xenbase_gene_lines(data_dict)

    if provider == "rgd" and resource in {"gene_variants", "alleles", "rat_alleles"}:
        return _rgd_gene_variants(data_dict)

    raise toolkit.ValidationError(
        {
            "provider": [
                toolkit._(
                    "Unsupported external lookup: provider=%(provider)r, resource=%(resource)r"
                )
                % {"provider": provider, "resource": resource}
            ]
        }
    )


@toolkit.side_effect_free
def xenbase_strains(context, data_dict):
    """Backward-compatible Xenbase lookup wrapper.

    Kept to avoid breaking existing schema or clients. Internally delegates to
    the generic `external_lookup()` action and reshapes the payload back to the
    historical `{"mutants": [...]}` format.
    """
    generic_payload = dict(data_dict or {})
    generic_payload.setdefault("provider", "xenbase")
    generic_payload.setdefault("resource", "gene_lines")
    result = external_lookup(context, generic_payload)
    return {"mutants": result.get("items", [])}


# ---------------------------------------------------------------------------
# Auth functions (registered via IAuthFunctions in plugin.py)
# ---------------------------------------------------------------------------


def xenbase_strains_auth(context, data_dict):
    """Allow any authenticated user to call the xenbase_strains action."""
    return {"success": bool(context.get("user") or context.get("auth_user_obj"))}


def external_lookup_auth(context, data_dict):
    """Allow any authenticated user to call the external_lookup action."""
    return {"success": bool(context.get("user") or context.get("auth_user_obj"))}
