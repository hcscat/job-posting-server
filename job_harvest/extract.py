from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any

import requests
from bs4 import BeautifulSoup

from job_harvest.models import JobPosting, SearchHit
from job_harvest.raw_store import RawSnapshotStore, SnapshotRef


TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class DetailFetchResult:
    posting: JobPosting
    listing_snapshot: SnapshotRef | None = None
    detail_snapshot: SnapshotRef | None = None
    html: str = ""


def fetch_job_details(
    headers: dict[str, str],
    hit: SearchHit,
    timeout_seconds: int,
    store_html: bool,
    raw_store: RawSnapshotStore | None = None,
) -> DetailFetchResult:
    posting = JobPosting(
        site_key=hit.site_key,
        site_name=hit.site_name,
        source_query=hit.source_query,
        discovered_at=hit.discovered_at,
        url=hit.url,
        normalized_url=hit.normalized_url,
        search_title=hit.search_title,
        search_snippet=hit.snippet,
        pub_date=hit.pub_date,
        company=hit.company,
        location=hit.location,
        employment_type=hit.employment_type,
        experience_level=hit.experience_level,
        education_level=hit.education_level,
        listing_snapshot_sha256=hit.listing_snapshot_sha256,
    )
    listing_snapshot = None
    detail_snapshot = None
    try:
        response = requests.get(hit.url, headers=headers, timeout=timeout_seconds)
        posting.status_code = response.status_code
        response.raise_for_status()
    except requests.RequestException:
        posting.title = hit.search_title
        posting.summary = hit.snippet
        posting.detail_fetched_at = datetime.now(timezone.utc).isoformat()
        return DetailFetchResult(posting=posting, listing_snapshot=listing_snapshot)

    html = response.text
    if raw_store is not None:
        detail_snapshot = raw_store.store_text(category="detail", url=hit.url, text=html)
        posting.detail_snapshot_sha256 = detail_snapshot.sha256_hex
    soup = BeautifulSoup(html, "html.parser")
    structured = extract_job_posting_from_json_ld(soup)

    posting.page_title = collapse_whitespace(soup.title.text) if soup.title else ""
    posting.title = structured.get("title") or extract_meta_content(
        soup, "property", ["og:title"]
    ) or extract_meta_content(soup, "name", ["twitter:title"]) or hit.search_title
    posting.company = structured.get("company") or posting.company
    posting.location = structured.get("location") or posting.location
    posting.employment_type = structured.get("employment_type") or posting.employment_type
    posting.date_posted = structured.get("date_posted", "")
    posting.valid_through = structured.get("valid_through", "")
    posting.description = structured.get("description", "")
    posting.summary = (
        structured.get("summary")
        or extract_meta_content(soup, "property", ["og:description"])
        or extract_meta_content(soup, "name", ["description", "twitter:description"])
        or hit.snippet
    )
    posting.extraction_method = structured.get("method", "meta")
    posting.tags = structured.get("tags", [])
    posting.detail_fetched_at = datetime.now(timezone.utc).isoformat()

    if not posting.description:
        posting.description = posting.summary

    return DetailFetchResult(
        posting=posting,
        listing_snapshot=listing_snapshot,
        detail_snapshot=detail_snapshot,
        html=html if store_html else "",
    )


def extract_job_posting_from_json_ld(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in iter_json_nodes(payload):
            node_type = normalize_type(node.get("@type"))
            if "jobposting" not in node_type:
                continue
            description = strip_html(node.get("description", ""))
            tags = []
            skills = node.get("skills")
            if isinstance(skills, list):
                tags = [collapse_whitespace(str(item)) for item in skills if str(item).strip()]
            elif isinstance(skills, str):
                tags = [
                    collapse_whitespace(part)
                    for part in re.split(r"[,/|]", skills)
                    if part.strip()
                ]

            return {
                "title": collapse_whitespace(node.get("title", "")),
                "company": extract_company(node.get("hiringOrganization")),
                "location": extract_location(node.get("jobLocation")),
                "employment_type": collapse_whitespace(stringify(node.get("employmentType"))),
                "date_posted": collapse_whitespace(stringify(node.get("datePosted"))),
                "valid_through": collapse_whitespace(stringify(node.get("validThrough"))),
                "description": description,
                "summary": description[:280],
                "tags": tags,
                "method": "json-ld",
            }
    return {}


def iter_json_nodes(payload: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            nodes.extend(iter_json_nodes(item))
        return nodes
    if isinstance(payload, dict):
        nodes.append(payload)
        graph = payload.get("@graph")
        if graph:
            nodes.extend(iter_json_nodes(graph))
    return nodes


def normalize_type(raw_type: Any) -> str:
    if isinstance(raw_type, list):
        return " ".join(str(item).casefold() for item in raw_type)
    return str(raw_type).casefold()


def extract_company(value: Any) -> str:
    if isinstance(value, dict):
        return collapse_whitespace(stringify(value.get("name")))
    return collapse_whitespace(stringify(value))


def extract_location(value: Any) -> str:
    locations: list[str] = []
    if isinstance(value, list):
        for item in value:
            text = extract_location(item)
            if text:
                locations.append(text)
        return ", ".join(dict.fromkeys(locations))
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            parts = [
                stringify(address.get("addressCountry")),
                stringify(address.get("addressRegion")),
                stringify(address.get("addressLocality")),
                stringify(address.get("streetAddress")),
            ]
            return ", ".join(part for part in map(collapse_whitespace, parts) if part)
        return collapse_whitespace(stringify(value.get("name")))
    return collapse_whitespace(stringify(value))


def extract_meta_content(
    soup: BeautifulSoup,
    attribute_name: str,
    attribute_values: list[str],
) -> str:
    for value in attribute_values:
        tag = soup.find("meta", attrs={attribute_name: value})
        if tag and tag.get("content"):
            return collapse_whitespace(unescape(tag["content"]))
    return ""


def strip_html(value: str) -> str:
    if not value:
        return ""
    text = TAG_RE.sub(" ", value)
    return collapse_whitespace(unescape(text))


def collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
