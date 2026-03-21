from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from job_harvest.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AppSettingsRecord(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    site_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    queries: Mapped[list[str]] = mapped_column(JSON, default=list)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    exclude_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    companies: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience_levels: Mapped[list[str]] = mapped_column(JSON, default=list)
    education_levels: Mapped[list[str]] = mapped_column(JSON, default=list)
    employment_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    extra_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    strict_match_groups: Mapped[list[str]] = mapped_column(JSON, default=list)

    max_results_per_site: Mapped[int] = mapped_column(Integer, default=8)
    request_timeout_seconds: Mapped[int] = mapped_column(Integer, default=20)
    fetch_details: Mapped[bool] = mapped_column(Boolean, default=True)
    store_html: Mapped[bool] = mapped_column(Boolean, default=False)
    concurrency: Mapped[int] = mapped_column(Integer, default=4)
    pause_between_searches_seconds: Mapped[float] = mapped_column(default=1.0)
    user_agent: Mapped[str] = mapped_column(Text, default="")
    output_dir: Mapped[str] = mapped_column(String(500), default="./data/exports")

    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_mode: Mapped[str] = mapped_column(String(50), default="fixed_times")
    schedule_times: Mapped[list[str]] = mapped_column(JSON, default=list)
    schedule_interval_hours: Mapped[int] = mapped_column(Integer, default=4)
    schedule_run_on_start: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_timezone: Mapped[str] = mapped_column(String(80), default="Asia/Seoul")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class CollectionRunRecord(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    triggered_by: Mapped[str] = mapped_column(String(50), default="manual")
    status: Mapped[str] = mapped_column(String(30), default="running")
    message: Mapped[str] = mapped_column(Text, default="")
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_hit_count: Mapped[int] = mapped_column(Integer, default=0)
    saved_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    query_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    site_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    export_path: Mapped[str] = mapped_column(String(500), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobPostingRecord(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    latest_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("collection_runs.id"),
        nullable=True,
    )

    normalized_url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    url: Mapped[str] = mapped_column(Text)
    site_key: Mapped[str] = mapped_column(String(50), index=True)
    site_name: Mapped[str] = mapped_column(String(100), index=True)
    source_query: Mapped[str] = mapped_column(Text, default="")

    title: Mapped[str] = mapped_column(Text, default="")
    search_title: Mapped[str] = mapped_column(Text, default="")
    search_snippet: Mapped[str] = mapped_column(Text, default="")
    page_title: Mapped[str] = mapped_column(Text, default="")
    company: Mapped[str] = mapped_column(String(255), default="", index=True)
    location: Mapped[str] = mapped_column(String(255), default="", index=True)
    employment_type: Mapped[str] = mapped_column(String(255), default="")
    experience_level: Mapped[str] = mapped_column(String(255), default="")
    education_level: Mapped[str] = mapped_column(String(255), default="")
    date_posted: Mapped[str] = mapped_column(String(120), default="")
    valid_through: Mapped[str] = mapped_column(String(120), default="")
    pub_date: Mapped[str] = mapped_column(String(120), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    extraction_method: Mapped[str] = mapped_column(String(80), default="search-result")
    status_code: Mapped[int] = mapped_column(Integer, default=0)
    html_path: Mapped[str] = mapped_column(String(500), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)

    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    seen_count: Mapped[int] = mapped_column(Integer, default=1)
