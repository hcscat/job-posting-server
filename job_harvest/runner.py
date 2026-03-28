from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from job_harvest.ai_enrichment import HeuristicEnricher, apply_enrichment, build_enricher
from job_harvest.config import AppConfig
from job_harvest.crawler import discover_job_hits
from job_harvest.extract import (
    DetailFetchResult,
    collect_jobplanet_details_with_browser,
    collect_rendered_details_with_browser,
    fetch_job_details,
)
from job_harvest.models import JobPosting, SearchHit
from job_harvest.raw_store import RawSnapshotStore
from job_harvest.storage import persist_run


@dataclass
class CollectionExecution:
    queries: list[str]
    hits: list[SearchHit]
    deduped_hits: list[SearchHit]
    skipped_existing_hits: list[SearchHit]
    detail_results: list[DetailFetchResult]
    all_postings: list[JobPosting]
    raw_manifest: list[dict[str, object]]
    relevant_postings: list[JobPosting]
    html_by_url: dict[str, str]
    listing_pages_fetched: int
    listing_snapshot_count: int
    detail_pages_fetched: int
    duplicate_skip_count: int
    raw_bytes_written: int
    ai_enriched_count: int


def run_collection(config: AppConfig) -> tuple[list[JobPosting], str]:
    execution = collect_postings(config)
    run_dir = persist_run(
        output_dir=config.output_dir,
        postings=execution.relevant_postings,
        all_postings=execution.all_postings,
        raw_manifest=execution.raw_manifest,
        queries=execution.queries,
        config_source=config.config_source,
        store_html=config.search.store_html,
        html_by_url=execution.html_by_url,
    )
    return execution.relevant_postings, str(run_dir)


def collect_postings(
    config: AppConfig,
    *,
    data_dir: str | Path | None = None,
    existing_detail_fetches: dict[str, datetime | None] | None = None,
) -> CollectionExecution:
    raw_store = RawSnapshotStore(data_dir or config.output_dir.parent)
    session = requests.Session()
    session.headers.update({"User-Agent": config.search.user_agent})

    discovery = discover_job_hits(config, session, raw_store)
    hits_to_fetch, skipped_existing_hits = split_hits_for_detail_refresh(
        discovery.deduped_hits,
        existing_detail_fetches or {},
        config.search.detail_refetch_hours,
    )
    detail_results = collect_details(config, session, hits_to_fetch, raw_store)

    enricher = build_enricher(config)
    fallback_enricher = HeuristicEnricher()
    ai_enriched_count = 0
    for result in detail_results:
        try:
            enrichment = enricher.enrich(result.posting)
            if enrichment.provider != "heuristic":
                ai_enriched_count += 1
        except Exception:
            enrichment = fallback_enricher.enrich(result.posting)
        apply_enrichment(result.posting, enrichment)

    relevant_postings = [
        result.posting
        for result in detail_results
        if is_relevant_posting(result.posting, config)
    ]
    all_postings = [result.posting for result in detail_results]
    raw_manifest = [
        {
            "site_key": result.posting.site_key,
            "site_name": result.posting.site_name,
            "normalized_url": result.posting.normalized_url,
            "url": result.posting.url,
            "title": result.posting.title or result.posting.search_title,
            "status_code": result.posting.status_code,
            "is_it_job": result.posting.is_it_job,
            "listing_snapshot_sha256": result.posting.listing_snapshot_sha256,
            "detail_snapshot_sha256": result.posting.detail_snapshot_sha256,
            "detail_fetched_at": result.posting.detail_fetched_at,
            "enriched_at": result.posting.enriched_at,
        }
        for result in detail_results
    ]
    html_by_url = {
        result.posting.normalized_url: result.html
        for result in detail_results
        if result.html and result.posting.is_it_job
    }
    raw_bytes_written = discovery.raw_bytes_written + sum(
        result.detail_snapshot.byte_size
        for result in detail_results
        if result.detail_snapshot and result.detail_snapshot.newly_written
    )
    return CollectionExecution(
        queries=discovery.queries,
        hits=discovery.hits,
        deduped_hits=discovery.deduped_hits,
        skipped_existing_hits=skipped_existing_hits,
        detail_results=detail_results,
        all_postings=all_postings,
        raw_manifest=raw_manifest,
        relevant_postings=relevant_postings,
        html_by_url=html_by_url,
        listing_pages_fetched=discovery.listing_pages_fetched,
        listing_snapshot_count=discovery.listing_snapshot_count,
        detail_pages_fetched=len(detail_results),
        duplicate_skip_count=len(skipped_existing_hits),
        raw_bytes_written=raw_bytes_written,
        ai_enriched_count=ai_enriched_count,
    )


def collect_details(
    config: AppConfig,
    session: requests.Session,
    hits: list[SearchHit],
    raw_store: RawSnapshotStore,
) -> list[DetailFetchResult]:
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
                    listing_snapshot_sha256=hit.listing_snapshot_sha256,
                )
            )
            for hit in hits
        ]

    headers = dict(session.headers)
    results: list[DetailFetchResult] = []
    jobplanet_hits: list[SearchHit] = []
    blind_hits: list[SearchHit] = []
    regular_hits: list[SearchHit] = []

    for hit in hits:
        if hit.site_key == "jobplanet":
            jobplanet_hits.append(hit)
        elif hit.site_key == "blind":
            blind_hits.append(hit)
        else:
            regular_hits.append(hit)

    results.extend(
        collect_jobplanet_details_with_browser(
            search_config=config.search,
            hits=jobplanet_hits,
            raw_store=raw_store,
        )
    )
    results.extend(
        collect_rendered_details_with_browser(
            search_config=config.search,
            hits=blind_hits,
            raw_store=raw_store,
        )
    )

    if not regular_hits:
        return results

    with ThreadPoolExecutor(max_workers=config.search.concurrency) as executor:
        futures = [
            executor.submit(
                fetch_job_details,
                config.search,
                headers,
                hit,
                raw_store,
            )
            for hit in regular_hits
        ]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def split_hits_for_detail_refresh(
    hits: list[SearchHit],
    existing_detail_fetches: dict[str, datetime | None],
    detail_refetch_hours: int,
) -> tuple[list[SearchHit], list[SearchHit]]:
    if not existing_detail_fetches:
        return hits, []

    threshold = datetime.now(timezone.utc) - timedelta(hours=detail_refetch_hours)
    to_fetch: list[SearchHit] = []
    skipped: list[SearchHit] = []
    for hit in hits:
        last_detail_fetch = existing_detail_fetches.get(hit.normalized_url)
        if last_detail_fetch is not None and last_detail_fetch >= threshold:
            skipped.append(hit)
            continue
        to_fetch.append(hit)
    return to_fetch, skipped


def is_relevant_posting(posting: JobPosting, config: AppConfig) -> bool:
    if config.search.crawl_strategy == "broad_it_scan":
        return posting.is_it_job
    return posting.is_it_job and matches_criteria(posting, config)


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
            posting.ai_summary,
            posting.ai_relevance_reason,
            posting.ai_job_family,
            " ".join(posting.tags),
            " ".join(posting.ai_tech_stack),
            " ".join(posting.ai_requirements),
            " ".join(posting.ai_responsibilities),
            " ".join(posting.ai_benefits),
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
