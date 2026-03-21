from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from job_harvest.config import DEFAULT_EXTRA_TERMS, DEFAULT_SITE_KEYS, DEFAULT_USER_AGENT
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
    concurrency: int = 4
    pause_between_searches_seconds: float = 1.0
    user_agent: str = DEFAULT_USER_AGENT
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

    @field_validator("max_results_per_site", "request_timeout_seconds", "concurrency", "schedule_interval_hours")
    @classmethod
    def validate_positive_ints(cls, value: int) -> int:
        return max(1, value)

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
    new_count: int
    updated_count: int
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
    discovered_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    seen_count: int


class JobListResponse(BaseModel):
    items: list[JobPostingRead]
    total: int
    page: int
    page_size: int


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
    is_collecting: bool
    site_counts: list[SiteCountRead]
    recent_runs: list[CollectionRunRead]
    scheduler: SchedulerStatusRead
