from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from job_harvest.models import SearchHit, SiteDefinition


TRACKING_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "trk",
    "tracking",
}

def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    normalized_path = parsed.path.rstrip("/") or "/"

    if host.endswith("linkedin.com"):
        host = "www.linkedin.com"
        query = ""
    elif host.endswith("teamblind.com"):
        host = "www.teamblind.com"
        query = ""
    elif host.endswith("jobkorea.co.kr") and normalized_path.lower().startswith("/recruit/gi_read/"):
        query = ""
    else:
        filtered = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_KEYS and not key.lower().startswith("utm_")
        ]
        query = urlencode(filtered, doseq=True)
    return urlunparse(
        (
            parsed.scheme.lower(),
            host,
            normalized_path,
            parsed.params,
            query,
            "",
        )
    )


def build_site_query(site: SiteDefinition, base_query: str) -> str:
    return f"site:{site.domain} {base_query}".strip()


def search_site(
    session: requests.Session,
    site: SiteDefinition,
    base_query: str,
    max_results: int,
    timeout_seconds: int,
) -> list[SearchHit]:
    direct_searchers = {
        "saramin": search_saramin,
        "jobkorea": search_jobkorea,
        "linkedin": search_linkedin,
    }
    searcher = direct_searchers.get(site.key, search_bing_rss)
    return searcher(
        session=session,
        site=site,
        base_query=base_query,
        max_results=max_results,
        timeout_seconds=timeout_seconds,
    )


def search_bing_rss(
    session: requests.Session,
    site: SiteDefinition,
    base_query: str,
    max_results: int,
    timeout_seconds: int,
) -> list[SearchHit]:
    query = build_site_query(site, base_query)
    url = f"https://www.bing.com/search?format=rss&q={quote(query)}"
    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    hits: list[SearchHit] = []
    discovered_at = datetime.now(timezone.utc).isoformat()
    for item in root.findall("./channel/item"):
        link = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        if not link:
            continue
        if site.domain.lower() not in urlparse(link).netloc.lower():
            continue
        hits.append(
            SearchHit(
                site_key=site.key,
                site_name=site.name,
                source_query=base_query,
                discovered_at=discovered_at,
                search_title=title,
                url=link,
                normalized_url=normalize_url(link),
                snippet=description,
                pub_date=pub_date,
                company="",
                location="",
                employment_type="",
                experience_level="",
                education_level="",
            )
        )
        if len(hits) >= max_results:
            break
    return hits


def search_saramin(
    session: requests.Session,
    site: SiteDefinition,
    base_query: str,
    max_results: int,
    timeout_seconds: int,
) -> list[SearchHit]:
    url = f"https://www.saramin.co.kr/zf_user/search/recruit?searchword={quote(base_query)}"
    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    discovered_at = datetime.now(timezone.utc).isoformat()
    hits_by_url: dict[str, SearchHit] = {}
    for card in soup.select("div.item_recruit"):
        anchor = card.select_one('h2.job_tit a[href*="/zf_user/jobs/relay/view"]')
        if not anchor or not anchor.get("href"):
            continue
        absolute_url = urljoin("https://www.saramin.co.kr", anchor["href"].strip())
        normalized = normalize_url(absolute_url)
        title = collapse_whitespace(anchor.get("title") or anchor.get_text(" ", strip=True))
        if not title:
            continue
        company = collapse_whitespace(
            (card.select_one(".corp_name a") or card.select_one(".corp_name")).get_text(
                " ",
                strip=True,
            )
        ) if card.select_one(".corp_name") else ""
        conditions = [
            collapse_whitespace(node.get_text(" ", strip=True))
            for node in card.select(".job_condition span")
            if collapse_whitespace(node.get_text(" ", strip=True))
        ]
        location = conditions[0] if conditions else ""
        experience_level = conditions[1] if len(conditions) >= 2 else ""
        education_level = conditions[2] if len(conditions) >= 3 else ""
        employment_type = conditions[3] if len(conditions) >= 4 else ""
        snippet = " | ".join(conditions)
        hits_by_url[normalized] = SearchHit(
            site_key=site.key,
            site_name=site.name,
            source_query=base_query,
            discovered_at=discovered_at,
            search_title=title,
            url=absolute_url,
            normalized_url=normalized,
            snippet=snippet,
            pub_date="",
            company=company,
            location=location,
            employment_type=employment_type,
            experience_level=experience_level,
            education_level=education_level,
        )
        if len(hits_by_url) >= max_results:
            break
    return list(hits_by_url.values())


def search_jobkorea(
    session: requests.Session,
    site: SiteDefinition,
    base_query: str,
    max_results: int,
    timeout_seconds: int,
) -> list[SearchHit]:
    url = f"https://www.jobkorea.co.kr/Search/?stext={quote(base_query)}"
    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return collect_anchor_hits(
        site=site,
        base_query=base_query,
        anchors=soup.select('a[href*="/Recruit/GI_Read/"]'),
        base_url="https://www.jobkorea.co.kr",
        max_results=max_results,
    )


def search_linkedin(
    session: requests.Session,
    site: SiteDefinition,
    base_query: str,
    max_results: int,
    timeout_seconds: int,
) -> list[SearchHit]:
    url = f"https://www.linkedin.com/jobs/search/?keywords={quote(base_query)}"
    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return collect_anchor_hits(
        site=site,
        base_query=base_query,
        anchors=soup.select('a[href*="/jobs/view/"]'),
        base_url="https://www.linkedin.com",
        max_results=max_results,
    )


def dedupe_hits(hits: Iterable[SearchHit]) -> list[SearchHit]:
    unique: list[SearchHit] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.normalized_url in seen:
            continue
        seen.add(hit.normalized_url)
        unique.append(hit)
    return unique


def pause_between_queries(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def collect_anchor_hits(
    site: SiteDefinition,
    base_query: str,
    anchors: Iterable,
    base_url: str,
    max_results: int,
) -> list[SearchHit]:
    discovered_at = datetime.now(timezone.utc).isoformat()
    hits_by_url: dict[str, SearchHit] = {}
    for anchor in anchors:
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute_url = urljoin(base_url, href)
        normalized = normalize_url(absolute_url)
        title = collapse_whitespace(anchor.get_text(" ", strip=True))
        if not title:
            continue
        existing = hits_by_url.get(normalized)
        if existing and len(existing.search_title) >= len(title):
            continue
        hits_by_url[normalized] = SearchHit(
            site_key=site.key,
            site_name=site.name,
            source_query=base_query,
            discovered_at=discovered_at,
            search_title=title,
            url=absolute_url,
            normalized_url=normalized,
            snippet="",
            pub_date="",
            company="",
            location="",
            employment_type="",
            experience_level="",
            education_level="",
        )
        if len(hits_by_url) >= max_results:
            break
    return list(hits_by_url.values())


def collapse_whitespace(value: str) -> str:
    return " ".join(value.split())
