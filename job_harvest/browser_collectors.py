from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse

from job_harvest.browser_runtime import BrowserSession, browser_runtime_available
from job_harvest.config import AppConfig
from job_harvest.models import SearchHit, SiteDefinition
from job_harvest.query_planner import has_active_filters
from job_harvest.raw_store import RawSnapshotStore
from job_harvest.search import collapse_whitespace, normalize_url


BROWSER_SITE_KEYS = {"jobplanet", "rocketpunch", "blind"}
JOBPLANET_BROAD_OCCUPATION_GROUPS = (
    ("jobplanet:development", {"occupation_level1": "11600"}),
    ("jobplanet:data", {"occupation_level1": "11912"}),
)
ROCKETPUNCH_FETCH_INIT = {
    "headers": {
        "accept": "application/json, text/plain, */*",
        "x-requested-with": "XMLHttpRequest",
    },
    "referrer": "https://www.rocketpunch.com/jobs",
}
BLIND_BROAD_TERMS = (
    "software engineer",
    "frontend",
    "backend",
    "fullstack",
    "data engineer",
    "data scientist",
    "machine learning",
    "devops",
)


@dataclass
class BrowserDiscoveryExecution:
    hits: list[SearchHit]
    listing_pages_fetched: int = 0
    listing_snapshot_count: int = 0
    raw_bytes_written: int = 0


def discover_site_hits_with_browser(
    *,
    config: AppConfig,
    raw_store: RawSnapshotStore,
    site: SiteDefinition,
    terms: list[str],
    location_hint: str | None,
) -> BrowserDiscoveryExecution:
    if not config.search.browser_enabled or not browser_runtime_available():
        return BrowserDiscoveryExecution(hits=[])
    if site.key == "jobplanet":
        return discover_jobplanet_hits(config=config, raw_store=raw_store, site=site, terms=terms)
    if site.key == "rocketpunch":
        return discover_rocketpunch_hits(config=config, raw_store=raw_store, site=site, terms=terms)
    if site.key == "blind":
        return discover_blind_hits(config=config, raw_store=raw_store, site=site, terms=terms)
    return BrowserDiscoveryExecution(hits=[])


def discover_jobplanet_hits(
    *,
    config: AppConfig,
    raw_store: RawSnapshotStore,
    site: SiteDefinition,
    terms: list[str],
) -> BrowserDiscoveryExecution:
    hits: list[SearchHit] = []
    listing_pages_fetched = 0
    listing_snapshot_count = 0
    raw_bytes_written = 0

    with BrowserSession(
        user_agent=config.search.user_agent,
        headless=config.search.browser_headless,
        timeout_seconds=config.search.browser_timeout_seconds,
    ) as browser:
        html, _ = browser.goto_html("https://www.jobplanet.co.kr/job", wait_ms=3500)
        snap_count, snap_bytes = _store_listing_snapshot(
            raw_store,
            "https://www.jobplanet.co.kr/job",
            html,
            "text/html; charset=utf-8",
        )
        listing_pages_fetched += 1
        listing_snapshot_count += snap_count
        raw_bytes_written += snap_bytes

        requests_to_run = build_jobplanet_requests(config, terms)
        for source_query, base_api_url in requests_to_run:
            discovered_at = _now_iso()
            page_number = 1
            max_pages = config.search.listing_page_limit or None
            while True:
                page_url = _replace_query_params(base_api_url, {"page": str(page_number)})
                body = browser.fetch_text(page_url)
                page_hits, total_pages = parse_jobplanet_jobs_payload(
                    body=body,
                    source_query=source_query,
                    discovered_at=discovered_at,
                )
                snap_count, snap_bytes = _store_listing_snapshot(
                    raw_store,
                    page_url,
                    body,
                    "application/json; charset=utf-8",
                    hits=page_hits,
                )
                listing_pages_fetched += 1
                listing_snapshot_count += snap_count
                raw_bytes_written += snap_bytes
                hits.extend(page_hits)

                if not page_hits:
                    break
                if max_pages is not None and page_number >= max_pages:
                    break
                if total_pages is not None and page_number >= total_pages:
                    break
                page_number += 1

    return BrowserDiscoveryExecution(
        hits=hits,
        listing_pages_fetched=listing_pages_fetched,
        listing_snapshot_count=listing_snapshot_count,
        raw_bytes_written=raw_bytes_written,
    )


def discover_rocketpunch_hits(
    *,
    config: AppConfig,
    raw_store: RawSnapshotStore,
    site: SiteDefinition,
    terms: list[str],
) -> BrowserDiscoveryExecution:
    hits: list[SearchHit] = []
    listing_pages_fetched = 0
    listing_snapshot_count = 0
    raw_bytes_written = 0
    seen_urls: set[str] = set()

    with BrowserSession(
        user_agent=config.search.user_agent,
        headless=config.search.browser_headless,
        timeout_seconds=config.search.browser_timeout_seconds,
    ) as browser:
        html, _ = browser.goto_html("https://www.rocketpunch.com/jobs", wait_ms=6000)
        snap_count, snap_bytes = _store_listing_snapshot(raw_store, "https://www.rocketpunch.com/jobs", html)
        listing_pages_fetched += 1
        listing_snapshot_count += snap_count
        raw_bytes_written += snap_bytes

        for source_query, keyword in build_rocketpunch_queries(config, terms):
            discovered_at = _now_iso()
            page_token = ""
            page_number = 1
            max_pages = config.search.listing_page_limit or None
            while True:
                params = {"sort": "DATE_DESC"}
                if keyword:
                    params["keyword"] = keyword
                if page_token:
                    params["pageToken"] = page_token
                api_url = _replace_query_params("https://www.rocketpunch.com/api/proxy/jobs", params)
                body = browser.fetch_text(api_url, init=ROCKETPUNCH_FETCH_INIT)
                page_hits, total_pages, next_page_token = parse_rocketpunch_jobs_payload(
                    body=body,
                    source_query=source_query,
                    discovered_at=discovered_at,
                )
                if page_number > 1 and not page_hits:
                    break
                page_hits = [hit for hit in page_hits if hit.normalized_url not in seen_urls]
                snap_count, snap_bytes = _store_listing_snapshot(
                    raw_store,
                    api_url,
                    body,
                    "application/json; charset=utf-8",
                    hits=page_hits,
                )
                listing_pages_fetched += 1
                listing_snapshot_count += snap_count
                raw_bytes_written += snap_bytes
                for hit in page_hits:
                    seen_urls.add(hit.normalized_url)
                hits.extend(page_hits)

                if not page_hits:
                    break
                if max_pages is not None and page_number >= max_pages:
                    break
                if total_pages is not None and page_number >= total_pages:
                    break
                if not next_page_token or next_page_token == page_token:
                    break
                page_token = next_page_token
                page_number += 1

    return BrowserDiscoveryExecution(
        hits=hits,
        listing_pages_fetched=listing_pages_fetched,
        listing_snapshot_count=listing_snapshot_count,
        raw_bytes_written=raw_bytes_written,
    )


def discover_blind_hits(
    *,
    config: AppConfig,
    raw_store: RawSnapshotStore,
    site: SiteDefinition,
    terms: list[str],
) -> BrowserDiscoveryExecution:
    hits: list[SearchHit] = []
    listing_pages_fetched = 0
    listing_snapshot_count = 0
    raw_bytes_written = 0
    rounds = config.search.listing_page_limit or 6
    wait_ms = max(int(config.search.pause_between_searches_seconds * 1000), 2000)
    seen_urls: set[str] = set()

    with BrowserSession(
        user_agent=config.search.user_agent,
        headless=config.search.browser_headless,
        timeout_seconds=config.search.browser_timeout_seconds,
    ) as browser:
        html, _ = browser.goto_html("https://www.teamblind.com/jobs", wait_ms=5000)
        snap_count, snap_bytes = _store_listing_snapshot(raw_store, "https://www.teamblind.com/jobs", html)
        listing_pages_fetched += 1
        listing_snapshot_count += snap_count
        raw_bytes_written += snap_bytes

        for source_query, search_term in build_blind_queries(config, terms):
            discovered_at = _now_iso()
            for page_number in range(1, rounds + 1):
                page_url = (
                    "https://www.teamblind.com/jobs"
                    f"?searchKeyword={quote(search_term)}&page={page_number}"
                )
                html, _ = browser.goto_html(page_url, wait_ms=wait_ms)
                rows = browser.page.eval_on_selector_all(
                    'a[href^="/jobs/"]',
                    """(elements) => elements.map((element) => {
                        const titleNode = element.querySelector('[data-testid="job-preview-title"]');
                        const locationNode = element.querySelector('[data-testid="job-preview-location"]');
                        const metadataNode = element.querySelector('[data-testid="job-preview-metadata"]');
                        const companyNode = metadataNode ? metadataNode.querySelector('[data-testid="company-name"]') : null;
                        return {
                            href: element.href,
                            text: (element.innerText || element.textContent || "").trim(),
                            title: titleNode ? (titleNode.innerText || titleNode.textContent || "").trim() : "",
                            company: companyNode ? (companyNode.innerText || companyNode.textContent || "").trim() : "",
                            location: locationNode ? (locationNode.innerText || locationNode.textContent || "").trim() : "",
                            metadata: metadataNode ? (metadataNode.innerText || metadataNode.textContent || "").trim() : ""
                        };
                    })""",
                )
                page_hits = parse_blind_job_cards(
                    rows=rows,
                    source_query=source_query,
                    discovered_at=discovered_at,
                )
                new_hits = [hit for hit in page_hits if hit.normalized_url not in seen_urls]
                snap_count, snap_bytes = _store_listing_snapshot(
                    raw_store,
                    page_url,
                    html,
                    hits=new_hits,
                )
                listing_pages_fetched += 1
                listing_snapshot_count += snap_count
                raw_bytes_written += snap_bytes
                for hit in new_hits:
                    seen_urls.add(hit.normalized_url)
                hits.extend(new_hits)
                if not page_hits:
                    break
                if new_hits and (len(new_hits) / max(len(page_hits), 1)) < 0.7:
                    break

    return BrowserDiscoveryExecution(
        hits=hits,
        listing_pages_fetched=listing_pages_fetched,
        listing_snapshot_count=listing_snapshot_count,
        raw_bytes_written=raw_bytes_written,
    )


def parse_jobplanet_jobs_payload(
    *,
    body: str,
    source_query: str,
    discovered_at: str,
) -> tuple[list[SearchHit], int | None]:
    payload = json.loads(body)
    data = payload.get("data") or {}
    jobs: list[dict] = []
    total = None
    page_size = None
    if isinstance(data.get("search_result"), dict):
        search_result = data["search_result"]
        meta = search_result.get("meta") or {}
        total = int(meta.get("total") or 0)
        jobs = list(search_result.get("jobs") or [])
        page_size = int(meta.get("page_size") or meta.get("per_page") or 50)
    else:
        total = int(data.get("total_count") or 0)
        jobs = list(data.get("recruits") or [])
        page_size = len(jobs) or 50

    hits: list[SearchHit] = []
    for item in jobs:
        job_id = _dig(item, "id") or _dig(item, "jd", "id")
        partial_url = _dig(item, "jd", "url") or _dig(item, "url") or ""
        if partial_url:
            absolute_url = urljoin("https://www.jobplanet.co.kr", str(partial_url))
        elif job_id:
            absolute_url = f"https://www.jobplanet.co.kr/job/search?posting_ids%5B%5D={job_id}"
        else:
            continue
        title = collapse_whitespace(str(_dig(item, "jd", "title") or _dig(item, "title") or ""))
        if not title:
            continue
        company = collapse_whitespace(
            str(_dig(item, "company", "name") or _dig(item, "jd", "company", "name") or "")
        )
        location = _join_names(_dig(item, "jd", "cities")) or collapse_whitespace(str(_dig(item, "company", "city_name") or ""))
        employment_type = collapse_whitespace(str(_dig(item, "jd", "job_type", "name") or _dig(item, "job_type") or ""))
        experience_level = _join_texts(_dig(item, "recruitment_text")) or _format_experience(_dig(item, "jd", "experience_years"))
        hits.append(
            SearchHit(
                site_key="jobplanet",
                site_name="JobPlanet",
                source_query=source_query,
                discovered_at=discovered_at,
                search_title=title,
                url=absolute_url,
                normalized_url=normalize_url(absolute_url),
                snippet=" | ".join(part for part in [employment_type, experience_level, location] if part),
                pub_date=collapse_whitespace(str(_dig(item, "jd", "created_at") or _dig(item, "created_at") or "")),
                company=company,
                location=location,
                employment_type=employment_type,
                experience_level=experience_level,
            )
        )
    total_pages = ceil(total / page_size) if total and page_size else None
    return hits, total_pages


def parse_rocketpunch_jobs_payload(
    *,
    body: str,
    source_query: str,
    discovered_at: str,
) -> tuple[list[SearchHit], int | None, str | None]:
    payload = json.loads(body)
    if payload.get("code") and not payload.get("items"):
        return [], None, None
    items = list(payload.get("items") or [])
    total_items = int(payload.get("totalItems") or 0)
    item_size = int(payload.get("itemSize") or len(items) or 20)
    page_token = collapse_whitespace(str(payload.get("pageToken") or ""))
    hits: list[SearchHit] = []
    for item in items:
        job_id = item.get("jobId")
        title = collapse_whitespace(str(item.get("title") or ""))
        if not job_id or not title:
            continue
        pseudo_url = f"https://www.rocketpunch.com/jobs?jobId={job_id}"
        seniorities = _join_texts(item.get("seniorities"))
        work_type = collapse_whitespace(str(item.get("workType") or ""))
        hits.append(
            SearchHit(
                site_key="rocketpunch",
                site_name="RocketPunch",
                source_query=source_query,
                discovered_at=discovered_at,
                search_title=title,
                url=pseudo_url,
                normalized_url=normalize_url(pseudo_url),
                snippet=collapse_whitespace(str(item.get("description") or "")),
                company=collapse_whitespace(str(item.get("companyName") or "")),
                employment_type=work_type,
                experience_level=seniorities,
            )
        )
    total_pages = ceil(total_items / item_size) if total_items and item_size else None
    return hits, total_pages, page_token or None


def parse_blind_anchor_rows(
    *,
    rows: list[dict[str, str]],
    source_query: str,
    discovered_at: str,
    term_filters: list[str] | None = None,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for row in rows:
        href = collapse_whitespace(row.get("href", ""))
        if not href or href.rstrip("/") == "https://www.teamblind.com/jobs":
            continue
        text = row.get("text", "")
        lowered = text.casefold()
        if term_filters and not any(term in lowered for term in term_filters):
            continue
        lines = [collapse_whitespace(line) for line in text.splitlines() if collapse_whitespace(line)]
        if not lines:
            continue
        title = lines[0]
        company = lines[1] if len(lines) >= 2 else ""
        location = lines[-1] if len(lines) >= 3 else ""
        hits.append(
            SearchHit(
                site_key="blind",
                site_name="Blind",
                source_query=source_query,
                discovered_at=discovered_at,
                search_title=title,
                url=href,
                normalized_url=normalize_url(href),
                snippet=" | ".join(lines[1:]),
                company=company,
                location=location,
            )
        )
    return hits


def parse_blind_job_cards(
    *,
    rows: list[dict[str, str]],
    source_query: str,
    discovered_at: str,
) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for row in rows:
        href = collapse_whitespace(row.get("href", ""))
        if not href:
            continue
        title = collapse_whitespace(row.get("title", ""))
        metadata = collapse_whitespace(row.get("metadata", ""))
        location = collapse_whitespace(row.get("location", ""))
        company = collapse_whitespace(row.get("company", ""))
        fallback_text = collapse_whitespace(row.get("text", ""))
        if not title and fallback_text:
            title = fallback_text.split("\n", 1)[0]
        if not title:
            continue
        hits.append(
            SearchHit(
                site_key="blind",
                site_name="Blind",
                source_query=source_query,
                discovered_at=discovered_at,
                search_title=title,
                url=href,
                normalized_url=normalize_url(href),
                snippet=" | ".join(part for part in [company, location, metadata] if part),
                company=company,
                location=location,
            )
        )
    return hits


def build_jobplanet_requests(config: AppConfig, terms: list[str]) -> list[tuple[str, str]]:
    if (config.search.crawl_strategy == "query_search" or has_active_filters(config.criteria)) and terms:
        requests_to_run: list[tuple[str, str]] = []
        for term in terms:
            requests_to_run.append(
                (
                    term,
                    _replace_query_params(
                        "https://www.jobplanet.co.kr/api/v3/job/search",
                        {
                            "query": term,
                            "page": "1",
                            "page_size": "1000",
                        },
                    ),
                )
            )
        return requests_to_run

    requests_to_run = []
    for source_query, params in JOBPLANET_BROAD_OCCUPATION_GROUPS:
        requests_to_run.append(
            (
                source_query,
                _replace_query_params(
                    "https://www.jobplanet.co.kr/api/v3/job/postings",
                    {
                        **params,
                        "order_by": "recent",
                        "page": "1",
                        "page_size": "1000",
                    },
                ),
            )
        )
    return requests_to_run


def build_rocketpunch_queries(
    config: AppConfig,
    terms: list[str],
) -> list[tuple[str, str]]:
    if config.search.crawl_strategy == "query_search" or has_active_filters(config.criteria):
        return [(term, term) for term in dedupe_terms(terms)]

    queries: list[tuple[str, str]] = [("__browser_all__", "")]
    for term in dedupe_terms(terms):
        queries.append((term, term))
    return queries


def build_blind_queries(
    config: AppConfig,
    terms: list[str],
) -> list[tuple[str, str]]:
    if config.search.crawl_strategy == "query_search" or has_active_filters(config.criteria):
        base_terms = dedupe_terms(terms)
    else:
        preferred = list(BLIND_BROAD_TERMS)
        base_terms = dedupe_terms(preferred + list(terms))
    return [(term, term) for term in base_terms]


def dedupe_terms(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        cleaned = collapse_whitespace(value)
        if not cleaned:
            continue
        marker = cleaned.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(cleaned)
    return unique


def _replace_query_params(url: str, updates: dict[str, str]) -> str:
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params.update(updates)
    return urlunparse(parsed._replace(query=urlencode(params)))


def _store_listing_snapshot(
    raw_store: RawSnapshotStore,
    url: str,
    text: str,
    content_type: str = "text/html; charset=utf-8",
    *,
    hits: list[SearchHit] | None = None,
) -> tuple[int, int]:
    snapshot = raw_store.store_text(category="listing", url=url, text=text, content_type=content_type)
    if hits:
        for hit in hits:
            hit.listing_snapshot_sha256 = snapshot.sha256_hex
    return 1, snapshot.byte_size if snapshot.newly_written else 0


def _dig(payload: dict, *keys: str):
    value = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _join_texts(value) -> str:
    if isinstance(value, list):
        return ", ".join(collapse_whitespace(str(item)) for item in value if collapse_whitespace(str(item)))
    return collapse_whitespace(str(value or ""))


def _join_names(items) -> str:
    if not isinstance(items, list):
        return ""
    return ", ".join(
        collapse_whitespace(str(item.get("name") or ""))
        for item in items
        if isinstance(item, dict) and collapse_whitespace(str(item.get("name") or ""))
    )


def _format_experience(value) -> str:
    if value in (None, "", 0):
        return ""
    return f"{value} years"


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
