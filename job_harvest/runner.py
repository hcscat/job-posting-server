from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable

import requests

from job_harvest.config import AppConfig, build_queries
from job_harvest.extract import DetailFetchResult, fetch_job_details
from job_harvest.models import JobPosting, SearchHit
from job_harvest.search import dedupe_hits, pause_between_queries, search_site
from job_harvest.sites import resolve_sites
from job_harvest.storage import persist_run


@dataclass
class CollectionExecution:
    queries: list[str]
    hits: list[SearchHit]
    deduped_hits: list[SearchHit]
    detail_results: list[DetailFetchResult]
    filtered_postings: list[JobPosting]
    html_by_url: dict[str, str]


def run_collection(config: AppConfig) -> tuple[list[JobPosting], str]:
    execution = collect_postings(config)
    run_dir = persist_run(
        output_dir=config.output_dir,
        postings=execution.filtered_postings,
        queries=execution.queries,
        config_source=config.config_source,
        store_html=config.search.store_html,
        html_by_url=execution.html_by_url,
    )
    return execution.filtered_postings, str(run_dir)


def collect_postings(config: AppConfig) -> CollectionExecution:
    queries = build_queries(config.criteria, config.search.queries)
    sites = resolve_sites(config.search.sites)
    session = requests.Session()
    session.headers.update({"User-Agent": config.search.user_agent})

    hits: list[SearchHit] = []
    for query in queries:
        for site in sites:
            try:
                site_hits = search_site(
                    session=session,
                    site=site,
                    base_query=query,
                    max_results=config.search.max_results_per_site,
                    timeout_seconds=config.search.request_timeout_seconds,
                )
            except Exception as exc:
                print(f"[job_harvest] search failed for {site.key}: {exc}", flush=True)
                site_hits = []
            hits.extend(site_hits)
            pause_between_queries(config.search.pause_between_searches_seconds)

    deduped_hits = dedupe_hits(hits)
    detail_results = collect_details(config, session, deduped_hits)
    postings = [result.posting for result in detail_results]
    filtered = [posting for posting in postings if matches_criteria(posting, config)]
    filtered_urls = {posting.normalized_url for posting in filtered}
    html_by_url = {
        result.posting.normalized_url: result.html
        for result in detail_results
        if result.html and result.posting.normalized_url in filtered_urls
    }
    return CollectionExecution(
        queries=queries,
        hits=hits,
        deduped_hits=deduped_hits,
        detail_results=detail_results,
        filtered_postings=filtered,
        html_by_url=html_by_url,
    )


def collect_details(
    config: AppConfig,
    session: requests.Session,
    hits: Iterable[SearchHit],
) -> list[DetailFetchResult]:
    hit_list = list(hits)
    if not config.search.fetch_details:
        return [
            DetailFetchResult(
                posting=JobPosting(
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
                    title=hit.search_title,
                    summary=hit.snippet,
                )
            )
            for hit in hit_list
        ]

    results: list[DetailFetchResult] = []
    with ThreadPoolExecutor(max_workers=config.search.concurrency) as executor:
        futures = [
            executor.submit(
                fetch_job_details,
                dict(session.headers),
                hit,
                config.search.request_timeout_seconds,
                config.search.store_html,
            )
            for hit in hit_list
        ]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def matches_criteria(posting: JobPosting, config: AppConfig) -> bool:
    criteria = config.criteria
    haystack = " ".join(
        [
            posting.title,
            posting.search_title,
            posting.search_snippet,
            posting.company,
            posting.location,
            posting.employment_type,
            posting.experience_level,
            posting.education_level,
            posting.summary,
            posting.description,
        ]
    ).casefold()

    for term in criteria.exclude_keywords:
        if term.casefold() in haystack:
            return False

    for term in criteria.required_terms:
        if term.casefold() not in haystack:
            return False

    groups = {
        "roles": criteria.roles,
        "keywords": criteria.keywords,
        "locations": criteria.locations,
        "companies": criteria.companies,
        "experience_levels": criteria.experience_levels,
        "education_levels": criteria.education_levels,
        "employment_types": criteria.employment_types,
    }
    for group_name in criteria.strict_match_groups:
        values = groups.get(group_name, [])
        if values and not any(value.casefold() in haystack for value in values):
            return False

    return True
