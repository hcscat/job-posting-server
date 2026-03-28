from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any

import requests
from bs4 import BeautifulSoup

from job_harvest.browser_runtime import BrowserSession, browser_runtime_available
from job_harvest.config import SearchConfig
from job_harvest.models import JobPosting, SearchHit
from job_harvest.raw_store import RawSnapshotStore, SnapshotRef


TAG_RE = re.compile(r"<[^>]+>")
JOBPLANET_POSTING_ID_RE = re.compile(r"(?:job_postings/|posting_ids%5B%5D=|posting_ids\[])(\d+)")
ROCKETPUNCH_JOB_ID_RE = re.compile(r"(?:jobId=|/jobs/)(\d+)")
DETAIL_HINTS = (
    "주요업무",
    "자격요건",
    "우대사항",
    "복지",
    "혜택",
    "기술스택",
    "requirements",
    "qualifications",
    "responsibilities",
    "benefits",
    "tech stack",
)


@dataclass
class DetailFetchResult:
    posting: JobPosting
    listing_snapshot: SnapshotRef | None = None
    detail_snapshot: SnapshotRef | None = None
    html: str = ""


def fetch_job_details(
    search_config: SearchConfig,
    headers: dict[str, str],
    hit: SearchHit,
    raw_store: RawSnapshotStore | None = None,
) -> DetailFetchResult:
    posting = init_posting_from_hit(hit)
    try:
        response = requests.get(hit.url, headers=headers, timeout=search_config.request_timeout_seconds)
        posting.status_code = response.status_code
        response.raise_for_status()
    except requests.RequestException:
        posting.title = hit.search_title
        posting.summary = hit.snippet
        posting.detail_fetched_at = datetime.now(timezone.utc).isoformat()
        return DetailFetchResult(posting=posting)

    return build_html_detail_result(
        posting=posting,
        hit=hit,
        html=response.text,
        raw_store=raw_store,
        store_html=search_config.store_html,
        status_code=posting.status_code,
    )


def collect_jobplanet_details_with_browser(
    search_config: SearchConfig,
    hits: list[SearchHit],
    raw_store: RawSnapshotStore | None = None,
) -> list[DetailFetchResult]:
    if not hits:
        return []
    if not search_config.browser_enabled or not browser_runtime_available():
        return [build_listing_only_result(hit, extraction_method="jobplanet-listing-only") for hit in hits]

    results: list[DetailFetchResult] = []
    with BrowserSession(
        user_agent=search_config.user_agent,
        headless=search_config.browser_headless,
        timeout_seconds=search_config.browser_timeout_seconds,
    ) as browser:
        browser.goto_html("https://www.jobplanet.co.kr/job", wait_ms=2500)
        for hit in hits:
            posting = init_posting_from_hit(hit)
            job_id = extract_jobplanet_posting_id(hit.url) or extract_jobplanet_posting_id(hit.normalized_url)
            if not job_id:
                results.append(build_listing_only_result(hit, extraction_method="jobplanet-listing-only", status_code=200))
                continue
            api_url = f"https://www.jobplanet.co.kr/api/v1/job/postings/{job_id}"
            try:
                body = browser.fetch_text(api_url)
                payload = json.loads(body)
            except Exception:
                results.append(build_listing_only_result(hit, extraction_method="jobplanet-listing-only", status_code=200))
                continue
            detail_snapshot = None
            if raw_store is not None:
                detail_snapshot = raw_store.store_text(
                    category="detail",
                    url=api_url,
                    text=body,
                    content_type="application/json; charset=utf-8",
                )
                posting.detail_snapshot_sha256 = detail_snapshot.sha256_hex
            apply_jobplanet_detail_payload(posting, payload.get("data") or {})
            posting.status_code = int(payload.get("code") or 200)
            posting.detail_fetched_at = datetime.now(timezone.utc).isoformat()
            results.append(DetailFetchResult(posting=posting, detail_snapshot=detail_snapshot))
    return results


def collect_rendered_details_with_browser(
    search_config: SearchConfig,
    hits: list[SearchHit],
    raw_store: RawSnapshotStore | None = None,
) -> list[DetailFetchResult]:
    if not hits:
        return []
    if not search_config.browser_enabled or not browser_runtime_available():
        return [build_listing_only_result(hit, extraction_method="browser-listing-only") for hit in hits]

    results: list[DetailFetchResult] = []
    with BrowserSession(
        user_agent=search_config.user_agent,
        headless=search_config.browser_headless,
        timeout_seconds=search_config.browser_timeout_seconds,
    ) as browser:
        for hit in hits:
            posting = init_posting_from_hit(hit)
            try:
                html, status_code = browser.goto_html(hit.url, wait_ms=3500)
            except Exception:
                results.append(build_listing_only_result(hit, extraction_method="browser-listing-only"))
                continue
            results.append(
                build_html_detail_result(
                    posting=posting,
                    hit=hit,
                    html=html,
                    raw_store=raw_store,
                    store_html=search_config.store_html,
                    status_code=status_code,
                )
            )
    return results


def collect_rocketpunch_details_with_browser(
    search_config: SearchConfig,
    hits: list[SearchHit],
    raw_store: RawSnapshotStore | None = None,
) -> list[DetailFetchResult]:
    if not hits:
        return []
    if not search_config.browser_enabled or not browser_runtime_available():
        return [build_listing_only_result(hit, extraction_method="rocketpunch-listing-only", status_code=200) for hit in hits]

    results: list[DetailFetchResult] = []
    with BrowserSession(
        user_agent=search_config.user_agent,
        headless=search_config.browser_headless,
        timeout_seconds=search_config.browser_timeout_seconds,
    ) as browser:
        browser.goto_html("https://www.rocketpunch.com/jobs", wait_ms=3000)
        for hit in hits:
            posting = init_posting_from_hit(hit)
            job_id = extract_rocketpunch_job_id(hit.url) or extract_rocketpunch_job_id(hit.normalized_url)
            if not job_id:
                results.append(build_listing_only_result(hit, extraction_method="rocketpunch-listing-only", status_code=200))
                continue
            api_url = f"https://www.rocketpunch.com/api/proxy/jobs/{job_id}"
            try:
                body = browser.fetch_text(
                    api_url,
                    init={
                        "headers": {
                            "accept": "application/json, text/plain, */*",
                            "x-requested-with": "XMLHttpRequest",
                        },
                        "referrer": "https://www.rocketpunch.com/jobs",
                    },
                )
                payload = json.loads(body)
            except Exception:
                results.append(build_listing_only_result(hit, extraction_method="rocketpunch-listing-only", status_code=200))
                continue
            if payload.get("code") and not payload.get("title"):
                results.append(build_listing_only_result(hit, extraction_method="rocketpunch-listing-only", status_code=200))
                continue
            detail_snapshot = None
            if raw_store is not None:
                detail_snapshot = raw_store.store_text(
                    category="detail",
                    url=api_url,
                    text=body,
                    content_type="application/json; charset=utf-8",
                )
                posting.detail_snapshot_sha256 = detail_snapshot.sha256_hex
            apply_rocketpunch_detail_payload(posting, payload)
            posting.status_code = 200
            posting.detail_fetched_at = datetime.now(timezone.utc).isoformat()
            results.append(DetailFetchResult(posting=posting, detail_snapshot=detail_snapshot))
    return results


def init_posting_from_hit(hit: SearchHit) -> JobPosting:
    return JobPosting(
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


def build_listing_only_result(
    hit: SearchHit,
    *,
    extraction_method: str,
    status_code: int = 0,
) -> DetailFetchResult:
    posting = init_posting_from_hit(hit)
    posting.status_code = status_code
    posting.title = hit.search_title
    posting.summary = hit.snippet
    posting.description = hit.snippet
    posting.extraction_method = extraction_method
    posting.detail_fetched_at = datetime.now(timezone.utc).isoformat()
    return DetailFetchResult(posting=posting)


def build_html_detail_result(
    *,
    posting: JobPosting,
    hit: SearchHit,
    html: str,
    raw_store: RawSnapshotStore | None,
    store_html: bool,
    status_code: int,
) -> DetailFetchResult:
    posting.status_code = status_code
    detail_snapshot = None
    if raw_store is not None:
        detail_snapshot = raw_store.store_text(category="detail", url=hit.url, text=html)
        posting.detail_snapshot_sha256 = detail_snapshot.sha256_hex

    populate_posting_from_html(posting, hit, html)
    posting.detail_fetched_at = datetime.now(timezone.utc).isoformat()
    return DetailFetchResult(
        posting=posting,
        detail_snapshot=detail_snapshot,
        html=html if store_html else "",
    )


def populate_posting_from_html(posting: JobPosting, hit: SearchHit, html: str) -> None:
    soup = BeautifulSoup(html, "html.parser")
    structured = extract_job_posting_from_json_ld(soup)
    extracted_description = select_best_description(
        structured.get("description", ""),
        extract_detail_text(soup),
    )

    posting.page_title = collapse_whitespace(soup.title.text) if soup.title else ""
    posting.title = structured.get("title") or extract_meta_content(
        soup, "property", ["og:title"]
    ) or extract_meta_content(soup, "name", ["twitter:title"]) or hit.search_title
    posting.company = structured.get("company") or posting.company
    posting.location = structured.get("location") or posting.location
    posting.employment_type = structured.get("employment_type") or posting.employment_type
    posting.date_posted = structured.get("date_posted", "")
    posting.valid_through = structured.get("valid_through", "")
    posting.description = extracted_description
    posting.summary = (
        structured.get("summary")
        or extract_meta_content(soup, "property", ["og:description"])
        or extract_meta_content(soup, "name", ["description", "twitter:description"])
        or summarize_excerpt(extracted_description)
        or hit.snippet
    )
    posting.extraction_method = structured.get(
        "method",
        "visible-text" if extracted_description else "meta",
    )
    posting.tags = structured.get("tags", [])
    if not posting.description:
        posting.description = posting.summary


def apply_jobplanet_detail_payload(posting: JobPosting, payload: dict[str, Any]) -> None:
    posting.title = collapse_whitespace(str(payload.get("title") or posting.search_title or ""))
    posting.page_title = posting.title
    posting.company = collapse_whitespace(str(payload.get("name") or posting.company or ""))
    posting.location = _join_values(payload.get("working_area")) or _join_values(payload.get("location")) or posting.location
    posting.employment_type = collapse_whitespace(str(payload.get("job_type") or posting.employment_type or ""))
    posting.experience_level = _join_values(payload.get("recruitment_text")) or posting.experience_level
    posting.date_posted = collapse_whitespace(str(payload.get("start_at") or ""))
    posting.valid_through = collapse_whitespace(str(payload.get("end_at") or ""))
    posting.summary = collapse_whitespace(str(payload.get("simple_comment") or "")) or posting.search_snippet
    posting.description = compose_jobplanet_description(payload)
    posting.extraction_method = "jobplanet-api"
    posting.tags = _extract_jobplanet_tags(payload)
    if not posting.summary:
        posting.summary = summarize_excerpt(posting.description)


def extract_jobplanet_posting_id(url: str) -> str | None:
    match = JOBPLANET_POSTING_ID_RE.search(url)
    return match.group(1) if match else None


def extract_rocketpunch_job_id(url: str) -> str | None:
    match = ROCKETPUNCH_JOB_ID_RE.search(url)
    return match.group(1) if match else None


def compose_jobplanet_description(payload: dict[str, Any]) -> str:
    sections: list[str] = []
    for label, value in (
        ("Introduction", payload.get("introduction")),
        ("Primary Responsibility", payload.get("primary_responsibility")),
        ("Required Qualification", payload.get("required_qualification")),
        ("Preferred Skill", payload.get("preferred_skill")),
        ("Benefit", payload.get("benefit")),
        ("Hiring Process", payload.get("hiring_process")),
        ("Culture", payload.get("culture")),
        ("Etc", payload.get("etc")),
        ("Appeal", payload.get("appeal")),
    ):
        text = _coerce_section_text(value)
        if text:
            sections.append(f"{label}\n{text}")
    return "\n\n".join(sections)


def apply_rocketpunch_detail_payload(posting: JobPosting, payload: dict[str, Any]) -> None:
    posting.title = collapse_whitespace(str(payload.get("title") or posting.search_title or ""))
    posting.page_title = posting.title
    posting.company = collapse_whitespace(str(payload.get("companyName") or posting.company or ""))
    posting.location = _join_values(payload.get("locations")) or collapse_whitespace(str(payload.get("location") or posting.location or ""))
    posting.employment_type = collapse_whitespace(str(payload.get("workType") or posting.employment_type or ""))
    posting.experience_level = _join_values(payload.get("seniorities")) or posting.experience_level
    posting.date_posted = collapse_whitespace(str(payload.get("createdAt") or payload.get("postedAt") or ""))
    posting.valid_through = collapse_whitespace(str(payload.get("expiresAt") or ""))
    posting.summary = collapse_whitespace(str(payload.get("shortDescription") or "")) or posting.search_snippet
    posting.description = compose_rocketpunch_description(payload)
    posting.extraction_method = "rocketpunch-api"
    posting.tags = _extract_rocketpunch_tags(payload)
    if not posting.description:
        posting.description = posting.summary
    if not posting.summary:
        posting.summary = summarize_excerpt(posting.description)


def compose_rocketpunch_description(payload: dict[str, Any]) -> str:
    sections: list[str] = []
    for label, value in (
        ("Description", payload.get("description")),
        ("Primary Responsibilities", payload.get("primaryResponsibilities")),
        ("Requirements", payload.get("requirements")),
        ("Preferred", payload.get("preferredQualifications")),
        ("Benefits", payload.get("benefits")),
        ("Tech Stack", payload.get("techStack")),
        ("Locations", payload.get("locations")),
    ):
        text = _coerce_section_text(value)
        if text:
            sections.append(f"{label}\n{text}")
    return "\n\n".join(sections)


def _extract_rocketpunch_tags(payload: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for value in (
        payload.get("jobCategories"),
        payload.get("skills"),
        payload.get("seniorities"),
        payload.get("techStack"),
    ):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    text = collapse_whitespace(
                        str(
                            item.get("name")
                            or item.get("title")
                            or item.get("value")
                            or ""
                        )
                    )
                else:
                    text = collapse_whitespace(str(item))
                if text:
                    tags.append(text)
        elif value:
            text = collapse_whitespace(str(value))
            if text:
                tags.append(text)
    return list(dict.fromkeys(tags))


def _extract_jobplanet_tags(payload: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for value in (payload.get("skills"), payload.get("keywords"), payload.get("preferred_skill")):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    text = collapse_whitespace(str(item.get("name") or item.get("keyword") or ""))
                else:
                    text = collapse_whitespace(str(item))
                if text:
                    tags.append(text)
        elif value:
            text = collapse_whitespace(str(value))
            if text:
                tags.append(text)
    return list(dict.fromkeys(tags))


def _coerce_section_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(collapse_whitespace(str(item)) for item in value if collapse_whitespace(str(item)))
    if isinstance(value, dict):
        return "\n".join(
            f"{collapse_whitespace(str(key))}: {collapse_whitespace(str(item))}"
            for key, item in value.items()
            if collapse_whitespace(str(item))
        )
    return collapse_whitespace(str(value or ""))


def _join_values(value: Any) -> str:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = collapse_whitespace(str(item.get("name") or item.get("text") or ""))
            else:
                text = collapse_whitespace(str(item))
            if text:
                items.append(text)
        return ", ".join(items)
    return collapse_whitespace(str(value or ""))


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


def extract_detail_text(soup: BeautifulSoup) -> str:
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for selector in ("main", "article", "section", "[role='main']"):
        for node in soup.select(selector)[:8]:
            for trash in node.select("script, style, noscript, svg"):
                trash.decompose()
            text = collapse_whitespace(node.get_text(" ", strip=True))
            if len(text) < 180:
                continue
            marker = text[:400].casefold()
            if marker in seen:
                continue
            seen.add(marker)
            lowered = text.casefold()
            score = min(len(text), 12000)
            score += 2000 * sum(1 for hint in DETAIL_HINTS if hint in lowered)
            candidates.append((score, text))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1][:12000]

    body_text = collapse_whitespace(soup.get_text(" ", strip=True))
    return body_text[:12000]


def select_best_description(structured_text: str, visible_text: str) -> str:
    structured_clean = collapse_whitespace(structured_text)
    visible_clean = collapse_whitespace(visible_text)
    if not structured_clean:
        return visible_clean
    if len(visible_clean) >= max(600, len(structured_clean) * 2):
        return visible_clean
    return structured_clean


def collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def summarize_excerpt(text: str, max_chars: int = 320) -> str:
    cleaned = collapse_whitespace(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
