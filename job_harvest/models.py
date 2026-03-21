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

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = ", ".join(self.tags)
        return payload
