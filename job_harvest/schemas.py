from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from job_harvest.config import (
    DEFAULT_EXTRA_TERMS,
    DEFAULT_IT_CRAWL_TERMS,
    DEFAULT_SITE_KEYS,
    DEFAULT_USER_AGENT,
)
from job_harvest.sites import DEFAULT_SITES


STRICT_MATCH_GROUPS = {
    "roles",
    "keywords",
    "locations",
    "companies",
    "experience_levels",
    "education_levels",
    "employment_types",
}
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_keys: list[str] = Field(default_factory=lambda: list(DEFAULT_SITE_KEYS))
    queries: list[str] = Field(default_factory=list)
    crawl_strategy: Literal["broad_it_scan", "query_search"] = "broad_it_scan"
    crawl_terms: list[str] = Field(default_factory=lambda: list(DEFAULT_IT_CRAWL_TERMS))
    listing_page_limit: int = 0
    roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    experience_levels: list[str] = Field(default_factory=list)
    education_levels: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    required_terms: list[str] = Field(default_factory=list)
    extra_terms: list[str] = Field(default_factory=lambda: list(DEFAULT_EXTRA_TERMS))
    strict_match_groups: list[str] = Field(default_factory=list)

    max_results_per_site: int = 8
    request_timeout_seconds: int = 20
    fetch_details: bool = True
    store_html: bool = False
    detail_refetch_hours: int = 24
    concurrency: int = 4
    pause_between_searches_seconds: float = 1.0
    ai_enrichment_enabled: bool = False
    ai_provider: Literal["heuristic", "openai"] = "heuristic"
    ai_model: str = ""
    user_agent: str = DEFAULT_USER_AGENT
    browser_enabled: bool = True
    browser_headless: bool = True
    browser_timeout_seconds: int = 60
    output_dir: str = "./data/exports"

    schedule_enabled: bool = False
    schedule_mode: Literal["fixed_times", "interval_hours"] = "fixed_times"
    schedule_times: list[str] = Field(default_factory=lambda: ["09:00"])
    schedule_interval_hours: int = 4
    schedule_run_on_start: bool = True
    schedule_timezone: str = "Asia/Seoul"

    @field_validator(
        "site_keys",
        "queries",
        "crawl_terms",
        "roles",
        "keywords",
        "exclude_keywords",
        "locations",
        "companies",
        "experience_levels",
        "education_levels",
        "employment_types",
        "required_terms",
        "extra_terms",
        "strict_match_groups",
    )
    @classmethod
    def strip_list_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @field_validator("site_keys")
    @classmethod
    def validate_sites(cls, values: list[str]) -> list[str]:
        unknown = [value for value in values if value not in DEFAULT_SITES]
        if unknown:
            raise ValueError(f"Unknown sites: {', '.join(sorted(unknown))}")
        return values

    @field_validator("strict_match_groups")
    @classmethod
    def validate_groups(cls, values: list[str]) -> list[str]:
        unknown = [value for value in values if value not in STRICT_MATCH_GROUPS]
        if unknown:
            raise ValueError(f"Unknown strict_match_groups: {', '.join(sorted(unknown))}")
        return values

    @field_validator("schedule_times")
    @classmethod
    def validate_times(cls, values: list[str]) -> list[str]:
        cleaned = values or ["09:00"]
        for value in cleaned:
            if not TIME_RE.match(value):
                raise ValueError("Schedule times must use HH:MM format.")
        return cleaned

    @field_validator(
        "listing_page_limit",
        "max_results_per_site",
        "request_timeout_seconds",
        "detail_refetch_hours",
        "concurrency",
        "browser_timeout_seconds",
        "schedule_interval_hours",
    )
    @classmethod
    def validate_positive_ints(cls, value: int) -> int:
        return max(0, value) if value == 0 else max(1, value)

    @field_validator("pause_between_searches_seconds")
    @classmethod
    def validate_pause(cls, value: float) -> float:
        return max(0.0, value)


class CollectionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    triggered_by: str
    status: str
    message: str
    hit_count: int
    unique_hit_count: int
    saved_count: int
    relevant_count: int
    new_count: int
    updated_count: int
    listing_page_count: int
    detail_page_count: int
    duplicate_skip_count: int
    ai_enriched_count: int
    raw_bytes_written: int
    query_terms: list[str]
    site_keys: list[str]
    export_path: str
    started_at: datetime
    finished_at: datetime | None


class JobPostingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    latest_run_id: int | None
    site_key: str
    site_name: str
    normalized_url: str
    url: str
    source_query: str
    title: str
    search_title: str
    company: str
    location: str
    employment_type: str
    experience_level: str
    education_level: str
    date_posted: str
    valid_through: str
    summary: str
    description: str
    extraction_method: str
    status_code: int
    tags: list[str]
    listing_snapshot_sha256: str
    detail_snapshot_sha256: str
    is_it_job: bool
    ai_provider: str
    ai_model: str
    ai_summary: str
    ai_relevance_reason: str
    ai_job_family: str
    ai_seniority: str
    ai_work_model: str
    ai_tech_stack: list[str]
    ai_requirements: list[str]
    ai_responsibilities: list[str]
    ai_benefits: list[str]
    discovered_at: datetime | None
    detail_fetched_at: datetime | None
    enriched_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    seen_count: int


class JobListResponse(BaseModel):
    items: list[JobPostingRead]
    total: int
    page: int
    page_size: int


class JobDetailRead(JobPostingRead):
    raw_payload: dict[str, Any] | None = None


class RunPostingRead(BaseModel):
    site_key: str = ""
    site_name: str = ""
    normalized_url: str = ""
    url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    status_code: int = 0
    is_it_job: bool = False
    listing_snapshot_sha256: str = ""
    detail_snapshot_sha256: str = ""


class RawManifestRead(BaseModel):
    site_key: str = ""
    site_name: str = ""
    normalized_url: str = ""
    url: str = ""
    title: str = ""
    status_code: int = 0
    is_it_job: bool = False
    listing_snapshot_sha256: str = ""
    detail_snapshot_sha256: str = ""
    detail_fetched_at: str = ""
    enriched_at: str = ""


class RunDetailRead(BaseModel):
    run: CollectionRunRead
    postings: list[RunPostingRead]
    raw_manifest: list[RawManifestRead]


class RawSnapshotRead(BaseModel):
    category: str
    sha256_hex: str
    text: str


class RequestInterpretPayload(BaseModel):
    text: str = Field(min_length=1)
    base_payload: SettingsPayload | None = None


class RequestInterpretRead(BaseModel):
    provider: str
    model: str
    notes: list[str]
    payload: SettingsPayload


class SiteCountRead(BaseModel):
    site_name: str
    count: int


class SchedulerJobRead(BaseModel):
    job_id: str
    description: str
    next_run_at: str | None


class SchedulerStatusRead(BaseModel):
    running: bool
    jobs: list[SchedulerJobRead]


class DashboardSummaryRead(BaseModel):
    total_postings: int
    total_runs: int
    pending_enrichment: int
    is_collecting: bool
    site_counts: list[SiteCountRead]
    recent_runs: list[CollectionRunRead]
    scheduler: SchedulerStatusRead
