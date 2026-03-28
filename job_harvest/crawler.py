from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from job_harvest.browser_collectors import BROWSER_SITE_KEYS, discover_site_hits_with_browser
from job_harvest.config import AppConfig, build_queries
from job_harvest.models import SearchHit, SiteDefinition
from job_harvest.raw_store import RawSnapshotStore
from job_harvest.search import collapse_whitespace, dedupe_hits, normalize_url, search_site
from job_harvest.sites import resolve_sites


WANTED_PAGE_SIZE = 50
SITEMAP_ENTRY_LIMIT = 50000
XML_NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass
class DiscoveryExecution:
    queries: list[str]
    hits: list[SearchHit]
    deduped_hits: list[SearchHit]
    listing_pages_fetched: int
    listing_snapshot_count: int
    raw_bytes_written: int


@dataclass
class SiteDiscoveryExecution:
    hits: list[SearchHit]
    listing_pages_fetched: int = 0
    listing_snapshot_count: int = 0
    raw_bytes_written: int = 0


SearchPageCrawlerFn = Callable[
    [requests.Session, str, int, str | None],
    tuple[str, list[SearchHit]],
]


SITEMAP_DISCOVERY_SOURCES: dict[str, dict[str, object]] = {
    "jumpit": {
        "urls": ["https://jumpit.saramin.co.kr/sitemap/sitemap_position_view_1.xml"],
        "patterns": [re.compile(r"/position/\d+$")],
    },
    "remember": {
        "urls": ["https://career.rememberapp.co.kr/sitemap-jobs.xml"],
        "patterns": [re.compile(r"/job/posting/\d+$")],
    },
}


def discover_job_hits(
    config: AppConfig,
    session: requests.Session,
    raw_store: RawSnapshotStore,
) -> DiscoveryExecution:
    sites = resolve_sites(config.search.sites)
    terms = build_discovery_terms(config)
    hits: list[SearchHit] = []
    listing_pages_fetched = 0
    listing_snapshot_count = 0
    raw_bytes_written = 0
    location_hint = next(iter(config.criteria.locations), None) or "South Korea"

    for site in sites:
        site_execution = discover_site_hits(
            config=config,
            session=session,
            raw_store=raw_store,
            site=site,
            terms=terms,
            location_hint=location_hint,
        )
        hits.extend(site_execution.hits)
        listing_pages_fetched += site_execution.listing_pages_fetched
        listing_snapshot_count += site_execution.listing_snapshot_count
        raw_bytes_written += site_execution.raw_bytes_written

    return DiscoveryExecution(
        queries=terms,
        hits=hits,
        deduped_hits=dedupe_hits(hits),
        listing_pages_fetched=listing_pages_fetched,
        listing_snapshot_count=listing_snapshot_count,
        raw_bytes_written=raw_bytes_written,
    )


def build_discovery_terms(config: AppConfig) -> list[str]:
    if config.search.crawl_strategy == "query_search":
        return build_queries(config.criteria, config.search.queries)
    return dedupe_terms(config.search.crawl_terms)


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


def discover_site_hits(
    *,
    config: AppConfig,
    session: requests.Session,
    raw_store: RawSnapshotStore,
    site: SiteDefinition,
    terms: list[str],
    location_hint: str | None,
) -> SiteDiscoveryExecution:
    if site.key in BROWSER_SITE_KEYS:
        browser_execution = discover_site_hits_with_browser(
            config=config,
            raw_store=raw_store,
            site=site,
            terms=terms,
            location_hint=location_hint,
        )
        if browser_execution.hits or config.search.browser_enabled:
            return SiteDiscoveryExecution(
                hits=browser_execution.hits,
                listing_pages_fetched=browser_execution.listing_pages_fetched,
                listing_snapshot_count=browser_execution.listing_snapshot_count,
                raw_bytes_written=browser_execution.raw_bytes_written,
            )

    if site.key in SITEMAP_DISCOVERY_SOURCES:
        return discover_site_hits_from_sitemaps(
            session=session,
            raw_store=raw_store,
            site=site,
            sitemap_urls=list(SITEMAP_DISCOVERY_SOURCES[site.key]["urls"]),
            allow_patterns=list(SITEMAP_DISCOVERY_SOURCES[site.key]["patterns"]),
            listing_page_limit=config.search.listing_page_limit,
        )

    crawler = SEARCH_PAGE_CRAWLERS.get(site.key)
    if crawler is not None:
        return discover_site_hits_from_search_pages(
            config=config,
            session=session,
            raw_store=raw_store,
            site=site,
            terms=terms,
            location_hint=location_hint,
            crawler=crawler,
        )

    return discover_site_hits_with_fallback_search(
        config=config,
        session=session,
        site=site,
        terms=terms,
    )


def discover_site_hits_from_search_pages(
    *,
    config: AppConfig,
    session: requests.Session,
    raw_store: RawSnapshotStore,
    site: SiteDefinition,
    terms: list[str],
    location_hint: str | None,
    crawler: SearchPageCrawlerFn,
) -> SiteDiscoveryExecution:
    hits: list[SearchHit] = []
    listing_pages_fetched = 0
    listing_snapshot_count = 0
    raw_bytes_written = 0

    for term in terms:
        page_number = 0
        consecutive_empty_pages = 0
        while True:
            if config.search.listing_page_limit and page_number >= config.search.listing_page_limit:
                break

            try:
                body_text, page_hits = crawler(session, term, page_number, location_hint)
            except requests.RequestException:
                break

            listing_pages_fetched += 1
            snapshot = raw_store.store_text(
                category="listing",
                url=f"{site.key}:{term}:{page_number}",
                text=body_text,
            )
            listing_snapshot_count += 1
            if snapshot.newly_written:
                raw_bytes_written += snapshot.byte_size

            if not page_hits:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 1:
                    break
            else:
                consecutive_empty_pages = 0
                for hit in page_hits:
                    hit.listing_snapshot_sha256 = snapshot.sha256_hex
                hits.extend(page_hits)

            page_number += 1
            if config.search.pause_between_searches_seconds > 0:
                time.sleep(config.search.pause_between_searches_seconds)

    return SiteDiscoveryExecution(
        hits=hits,
        listing_pages_fetched=listing_pages_fetched,
        listing_snapshot_count=listing_snapshot_count,
        raw_bytes_written=raw_bytes_written,
    )


def discover_site_hits_from_sitemaps(
    *,
    session: requests.Session,
    raw_store: RawSnapshotStore,
    site: SiteDefinition,
    sitemap_urls: list[str],
    allow_patterns: list[re.Pattern[str]],
    listing_page_limit: int,
) -> SiteDiscoveryExecution:
    discovered_at = datetime.now(timezone.utc).isoformat()
    queue: deque[str] = deque(sitemap_urls)
    seen_sitemaps: set[str] = set()
    seen_urls: set[str] = set()
    hits: list[SearchHit] = []
    listing_pages_fetched = 0
    listing_snapshot_count = 0
    raw_bytes_written = 0

    while queue:
        if listing_page_limit and listing_pages_fetched >= listing_page_limit:
            break

        sitemap_url = queue.popleft()
        normalized_sitemap_url = normalize_url(sitemap_url)
        if normalized_sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(normalized_sitemap_url)

        try:
            response = session.get(sitemap_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException:
            continue

        xml_text = response.text
        listing_pages_fetched += 1
        snapshot = raw_store.store_text(
            category="listing",
            url=sitemap_url,
            text=xml_text,
            content_type=response.headers.get("Content-Type", "application/xml"),
        )
        listing_snapshot_count += 1
        if snapshot.newly_written:
            raw_bytes_written += snapshot.byte_size

        for entry_type, loc, lastmod in iter_sitemap_entries(xml_text):
            if entry_type == "sitemap":
                queue.append(loc)
                continue
            if not any(pattern.search(loc) for pattern in allow_patterns):
                continue
            normalized_url = normalize_url(loc)
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            hits.append(
                SearchHit(
                    site_key=site.key,
                    site_name=site.name,
                    source_query="__sitemap__",
                    discovered_at=discovered_at,
                    search_title="",
                    url=loc,
                    normalized_url=normalized_url,
                    snippet="",
                    pub_date=lastmod,
                    listing_snapshot_sha256=snapshot.sha256_hex,
                )
            )
            if len(seen_urls) >= SITEMAP_ENTRY_LIMIT:
                break

        if len(seen_urls) >= SITEMAP_ENTRY_LIMIT:
            break

    return SiteDiscoveryExecution(
        hits=hits,
        listing_pages_fetched=listing_pages_fetched,
        listing_snapshot_count=listing_snapshot_count,
        raw_bytes_written=raw_bytes_written,
    )


def discover_site_hits_with_fallback_search(
    *,
    config: AppConfig,
    session: requests.Session,
    site: SiteDefinition,
    terms: list[str],
) -> SiteDiscoveryExecution:
    hits: list[SearchHit] = []
    max_results = max(config.search.max_results_per_site, 25)
    for term in terms:
        try:
            hits.extend(
                search_site(
                    session=session,
                    site=site,
                    base_query=term,
                    max_results=max_results,
                    timeout_seconds=config.search.request_timeout_seconds,
                )
            )
        except requests.RequestException:
            continue
        if config.search.pause_between_searches_seconds > 0:
            time.sleep(config.search.pause_between_searches_seconds)
    return SiteDiscoveryExecution(hits=hits)


def iter_sitemap_entries(xml_text: str) -> list[tuple[str, str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    local_name = root.tag.rsplit("}", 1)[-1]
    if local_name == "sitemapindex":
        return [
            (
                "sitemap",
                collapse_whitespace(item.findtext("sm:loc", default="", namespaces=XML_NAMESPACE)),
                collapse_whitespace(item.findtext("sm:lastmod", default="", namespaces=XML_NAMESPACE)),
            )
            for item in root.findall("sm:sitemap", XML_NAMESPACE)
            if collapse_whitespace(item.findtext("sm:loc", default="", namespaces=XML_NAMESPACE))
        ]

    if local_name == "urlset":
        return [
            (
                "url",
                collapse_whitespace(item.findtext("sm:loc", default="", namespaces=XML_NAMESPACE)),
                collapse_whitespace(item.findtext("sm:lastmod", default="", namespaces=XML_NAMESPACE)),
            )
            for item in root.findall("sm:url", XML_NAMESPACE)
            if collapse_whitespace(item.findtext("sm:loc", default="", namespaces=XML_NAMESPACE))
        ]

    return []


def crawl_saramin(
    session: requests.Session,
    term: str,
    page_number: int,
    location_hint: str | None,
) -> tuple[str, list[SearchHit]]:
    page = page_number + 1
    url = (
        f"https://www.saramin.co.kr/zf_user/search/recruit?searchword={quote(term)}"
        f"&recruitPage={page}"
    )
    response = session.get(url, timeout=30)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    discovered_at = datetime.now(timezone.utc).isoformat()
    hits: list[SearchHit] = []

    for card in soup.select("div.item_recruit"):
        anchor = card.select_one('h2.job_tit a[href*="/zf_user/jobs/relay/view"]')
        if not anchor or not anchor.get("href"):
            continue
        absolute_url = urljoin("https://www.saramin.co.kr", anchor["href"].strip())
        title = collapse_whitespace(anchor.get("title") or anchor.get_text(" ", strip=True))
        if not title:
            continue
        company_node = card.select_one(".corp_name a") or card.select_one(".corp_name")
        company = collapse_whitespace(company_node.get_text(" ", strip=True)) if company_node else ""
        conditions = [
            collapse_whitespace(node.get_text(" ", strip=True))
            for node in card.select(".job_condition span")
            if collapse_whitespace(node.get_text(" ", strip=True))
        ]
        hits.append(
            SearchHit(
                site_key="saramin",
                site_name="사람인",
                source_query=term,
                discovered_at=discovered_at,
                search_title=title,
                url=absolute_url,
                normalized_url=normalize_url(absolute_url),
                snippet=" | ".join(conditions),
                company=company,
                location=conditions[0] if len(conditions) >= 1 else "",
                experience_level=conditions[1] if len(conditions) >= 2 else "",
                education_level=conditions[2] if len(conditions) >= 3 else "",
                employment_type=conditions[3] if len(conditions) >= 4 else "",
            )
        )
    return html, hits


def crawl_jobkorea(
    session: requests.Session,
    term: str,
    page_number: int,
    location_hint: str | None,
) -> tuple[str, list[SearchHit]]:
    page = page_number + 1
    url = f"https://www.jobkorea.co.kr/Search/?stext={quote(term)}&Page_No={page}"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    discovered_at = datetime.now(timezone.utc).isoformat()
    hits: list[SearchHit] = []

    for anchor in soup.select('a[href*="/Recruit/GI_Read/"]'):
        href = (anchor.get("href") or "").strip()
        title = collapse_whitespace(anchor.get_text(" ", strip=True))
        if not href or not title:
            continue
        card = anchor.find_parent(["article", "li", "div"])
        company = ""
        location = ""
        if card:
            company_node = card.select_one(".corp-name") or card.select_one(".name")
            location_node = card.select_one(".chip-information-group .chip-information:nth-of-type(1)")
            company = collapse_whitespace(company_node.get_text(" ", strip=True)) if company_node else ""
            location = collapse_whitespace(location_node.get_text(" ", strip=True)) if location_node else ""

        absolute_url = urljoin("https://www.jobkorea.co.kr", href)
        hits.append(
            SearchHit(
                site_key="jobkorea",
                site_name="잡코리아",
                source_query=term,
                discovered_at=discovered_at,
                search_title=title,
                url=absolute_url,
                normalized_url=normalize_url(absolute_url),
                company=company,
                location=location,
            )
        )
    return html, hits


def crawl_linkedin(
    session: requests.Session,
    term: str,
    page_number: int,
    location_hint: str | None,
) -> tuple[str, list[SearchHit]]:
    start = page_number * 10
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={quote(term)}&location={quote(location_hint or 'South Korea')}&start={start}"
    )
    response = session.get(url, timeout=30)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    discovered_at = datetime.now(timezone.utc).isoformat()
    hits: list[SearchHit] = []

    for card in soup.select("li"):
        anchor = card.select_one('a[href*="/jobs/view/"]')
        if not anchor or not anchor.get("href"):
            continue
        title = collapse_whitespace(anchor.get_text(" ", strip=True))
        if not title:
            continue
        company_node = card.select_one(".base-search-card__subtitle")
        location_node = card.select_one(".job-search-card__location")
        absolute_url = urljoin("https://www.linkedin.com", anchor["href"].strip())
        hits.append(
            SearchHit(
                site_key="linkedin",
                site_name="LinkedIn",
                source_query=term,
                discovered_at=discovered_at,
                search_title=title,
                url=absolute_url,
                normalized_url=normalize_url(absolute_url),
                company=collapse_whitespace(company_node.get_text(" ", strip=True)) if company_node else "",
                location=collapse_whitespace(location_node.get_text(" ", strip=True)) if location_node else "",
            )
        )
    return html, hits


def crawl_wanted(
    session: requests.Session,
    term: str,
    page_number: int,
    location_hint: str | None,
) -> tuple[str, list[SearchHit]]:
    offset = page_number * WANTED_PAGE_SIZE
    url = "https://www.wanted.co.kr/api/chaos/search/v1/position"
    response = session.get(
        url,
        params={"query": term, "limit": WANTED_PAGE_SIZE, "offset": offset},
        headers={"Referer": f"https://www.wanted.co.kr/search?query={quote(term)}"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    discovered_at = datetime.now(timezone.utc).isoformat()
    hits: list[SearchHit] = []

    for item in payload.get("data", []):
        position_id = item.get("id")
        title = collapse_whitespace(str(item.get("position", "")))
        if not position_id or not title:
            continue
        absolute_url = f"https://www.wanted.co.kr/wd/{position_id}"
        company_payload = item.get("company") or {}
        hits.append(
            SearchHit(
                site_key="wanted",
                site_name="원티드",
                source_query=term,
                discovered_at=discovered_at,
                search_title=title,
                url=absolute_url,
                normalized_url=normalize_url(absolute_url),
                company=collapse_whitespace(str(company_payload.get("name", ""))),
                employment_type=collapse_whitespace(str(item.get("employment_type", ""))),
            )
        )
    return json.dumps(payload, ensure_ascii=False), hits


SEARCH_PAGE_CRAWLERS: dict[str, SearchPageCrawlerFn] = {
    "saramin": crawl_saramin,
    "jobkorea": crawl_jobkorea,
    "linkedin": crawl_linkedin,
    "wanted": crawl_wanted,
}
