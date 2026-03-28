from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SiteDefinition:
    key: str
    name: str
    domain: str


@dataclass
class SearchHit:
    site_key: str
    site_name: str
    source_query: str
    discovered_at: str
    search_title: str
    url: str
    normalized_url: str
    snippet: str = ""
    pub_date: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    experience_level: str = ""
    education_level: str = ""
    listing_snapshot_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JobPosting:
    site_key: str
    site_name: str
    source_query: str
    discovered_at: str
    url: str
    normalized_url: str
    search_title: str = ""
    search_snippet: str = ""
    pub_date: str = ""
    page_title: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    experience_level: str = ""
    education_level: str = ""
    date_posted: str = ""
    valid_through: str = ""
    summary: str = ""
    description: str = ""
    extraction_method: str = "search-result"
    status_code: int = 0
    html_path: str = ""
    tags: list[str] = field(default_factory=list)
    listing_snapshot_sha256: str = ""
    detail_snapshot_sha256: str = ""
    is_it_job: bool = True
    ai_provider: str = ""
    ai_model: str = ""
    ai_summary: str = ""
    ai_relevance_reason: str = ""
    ai_job_family: str = ""
    ai_seniority: str = ""
    ai_work_model: str = ""
    ai_tech_stack: list[str] = field(default_factory=list)
    ai_requirements: list[str] = field(default_factory=list)
    ai_responsibilities: list[str] = field(default_factory=list)
    ai_benefits: list[str] = field(default_factory=list)
    detail_fetched_at: str = ""
    enriched_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = ", ".join(self.tags)
        payload["ai_tech_stack"] = ", ".join(self.ai_tech_stack)
        payload["ai_requirements"] = ", ".join(self.ai_requirements)
        payload["ai_responsibilities"] = ", ".join(self.ai_responsibilities)
        payload["ai_benefits"] = ", ".join(self.ai_benefits)
        return payload
