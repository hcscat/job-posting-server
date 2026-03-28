from __future__ import annotations

import json
from dataclasses import dataclass
from math import ceil
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse

from job_harvest.browser_runtime import BrowserSession, browser_runtime_available
from job_harvest.config import AppConfig
from job_harvest.models import SearchHit, SiteDefinition
from job_harvest.raw_store import RawSnapshotStore
from job_harvest.search import collapse_whitespace, normalize_url


BROWSER_SITE_KEYS = {"jobplanet", "rocketpunch", "blind"}


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
        return discover_rocketpunch_hits(config=config, raw_store=raw_store, site=site)
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
    selected_terms = terms if config.search.crawl_strategy == "query_search" and terms else (terms[:1] or ["developer"])
    hits: list[SearchHit] = []
    listing_pages_fetched = 0
    listing_snapshot_count = 0
    raw_bytes_written = 0

    with BrowserSession(
        user_agent=config.search.user_agent,
        headless=config.search.browser_headless,
        timeout_seconds=config.search.browser_timeout_seconds,
    ) as browser:
        for term in selected_terms:
            discovered_at = _now_iso()
            search_url = f"https://www.jobplanet.co.kr/job/search?query={quote(term)}"
            api_urls: list[str] = []

            def handle_response(response) -> None:
                if "/api/v3/job/search" in response.url and response.status == 200 and response.url not in api_urls:
                    api_urls.append(response.url)

            browser.page.on("response", handle_response)
            html, _ = browser.goto_html(search_url, wait_ms=5000)
            snap_count, snap_bytes = _store_listing_snapshot(raw_store, search_url, html, "text/html; charset=utf-8")
            listing_pages_fetched += 1
            listing_snapshot_count += snap_count
            raw_bytes_written += snap_bytes

            if not api_urls:
                browser.page.remove_listener("response", handle_response)
                continue

            first_api_url = _replace_query_params(api_urls[0], {"page": "1", "page_size": "50"})
            page_number = 1
            max_pages = config.search.listing_page_limit or None
            while True:
                page_url = _replace_query_params(first_api_url, {"page": str(page_number)})
                body = browser.fetch_text(page_url)
                page_hits, total_pages = parse_jobplanet_jobs_payload(
                    body=body,
                    source_query=term,
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
            browser.page.remove_listener("response", handle_response)

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
) -> BrowserDiscoveryExecution:
    hits: list[SearchHit] = []
    listing_pages_fetched = 0
    listing_snapshot_count = 0
    raw_bytes_written = 0
    discovered_at = _now_iso()

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

        first_url = "https://www.rocketpunch.com/api/proxy/jobs?sort=DATE_DESC"
        page_number = 1
        max_pages = config.search.listing_page_limit or None
        while True:
            api_url = first_url if page_number == 1 else f"{first_url}&page={page_number}"
            body = browser.fetch_text(api_url)
            page_hits, total_pages = parse_rocketpunch_jobs_payload(
                body=body,
                source_query="__browser_all__",
                discovered_at=discovered_at,
            )
            if page_number > 1 and not page_hits:
                break
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
            hits.extend(page_hits)

            if max_pages is not None and page_number >= max_pages:
                break
            if total_pages is not None and page_number >= total_pages:
                break
            if page_number >= 2 and not page_hits:
                break
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
    discovered_at = _now_iso()
    rounds = config.search.listing_page_limit or 25
    wait_ms = max(int(config.search.pause_between_searches_seconds * 1000), 1500)
    term_filters = [term.casefold() for term in terms] if config.search.crawl_strategy == "query_search" else []
    seen_urls: set[str] = set()
    stagnant_rounds = 0

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

        for round_index in range(rounds):
            rows = browser.page.eval_on_selector_all(
                'a[href*="/jobs/"]',
                """(elements) => elements.map((element) => ({
                    href: element.href,
                    text: (element.innerText || element.textContent || "").trim()
                }))""",
            )
            page_hits = parse_blind_anchor_rows(
                rows=rows,
                source_query="__browser_all__",
                discovered_at=discovered_at,
                term_filters=term_filters,
            )
            before = len(seen_urls)
            for hit in page_hits:
                if hit.normalized_url in seen_urls:
                    continue
                seen_urls.add(hit.normalized_url)
                hits.append(hit)
            if len(seen_urls) == before:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
            if stagnant_rounds >= 3:
                break
            browser.page.mouse.wheel(0, 9000)
            browser.page.wait_for_timeout(wait_ms)
            html = browser.page.content()
            snap_count, snap_bytes = _store_listing_snapshot(
                raw_store,
                f"https://www.teamblind.com/jobs#round={round_index + 1}",
                html,
            )
            listing_pages_fetched += 1
            listing_snapshot_count += snap_count
            raw_bytes_written += snap_bytes

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
) -> tuple[list[SearchHit], int | None]:
    payload = json.loads(body)
    items = list(payload.get("items") or [])
    total_items = int(payload.get("totalItems") or 0)
    item_size = int(payload.get("itemSize") or len(items) or 20)
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
    return hits, total_pages


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
