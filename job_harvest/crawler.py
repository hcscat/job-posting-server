from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import Callable, Iterable
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from job_harvest.config import AppConfig, build_queries
from job_harvest.models import SearchHit
from job_harvest.raw_store import RawSnapshotStore
from job_harvest.search import collapse_whitespace, dedupe_hits, normalize_url
from job_harvest.sites import resolve_sites


@dataclass
class DiscoveryExecution:
    queries: list[str]
    hits: list[SearchHit]
    deduped_hits: list[SearchHit]
    listing_pages_fetched: int
    listing_snapshot_count: int
    raw_bytes_written: int


CrawlerFn = Callable[[requests.Session, str, int, str | None], tuple[str, list[SearchHit]]]


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

    for term in terms:
        for site in sites:
            crawler = DIRECT_CRAWLERS.get(site.key)
            if crawler is None:
                continue

            seen_urls_for_site: set[str] = set()
            page_number = 0
            while True:
                if config.search.listing_page_limit and page_number >= config.search.listing_page_limit:
                    break

                html, page_hits = crawler(session, term, page_number, location_hint)
                listing_pages_fetched += 1
                snapshot = raw_store.store_text(
                    category="listing",
                    url=f"{site.key}:{term}:{page_number}",
                    text=html,
                )
                listing_snapshot_count += 1
                if snapshot.newly_written:
                    raw_bytes_written += snapshot.byte_size

                new_page_hits: list[SearchHit] = []
                for hit in page_hits:
                    hit.listing_snapshot_sha256 = snapshot.sha256_hex
                    if hit.normalized_url in seen_urls_for_site:
                        continue
                    seen_urls_for_site.add(hit.normalized_url)
                    new_page_hits.append(hit)

                if not new_page_hits:
                    break

                hits.extend(new_page_hits)
                page_number += 1
                if config.search.pause_between_searches_seconds > 0:
                    time.sleep(config.search.pause_between_searches_seconds)

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
    title = collapse_whitespace(soup.title.get_text(" ", strip=True)) if soup.title else ""
    if "0건의 검색결과" in title:
        return html, []

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
    url = f"https://www.jobkorea.co.kr/Search/?stext={quote(term)}&Page_No={page_number}"
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


DIRECT_CRAWLERS: dict[str, CrawlerFn] = {
    "saramin": crawl_saramin,
    "jobkorea": crawl_jobkorea,
    "linkedin": crawl_linkedin,
}
