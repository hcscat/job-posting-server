from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_SITE_KEYS = ["saramin", "jobkorea", "linkedin"]
DEFAULT_EXTRA_TERMS = ["채용", "공고"]
DEFAULT_IT_CRAWL_TERMS = [
    "개발",
    "웹 개발",
    "앱 개발",
    "데이터",
    "보안",
    "클라우드",
    "frontend",
    "backend",
    "fullstack",
    "소프트웨어 엔지니어",
    "software engineer",
    "DevOps",
    "data engineer",
    "machine learning",
]
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


@dataclass
class SearchConfig:
    sites: list[str] = field(default_factory=lambda: list(DEFAULT_SITE_KEYS))
    queries: list[str] = field(default_factory=list)
    crawl_strategy: str = "broad_it_scan"
    crawl_terms: list[str] = field(default_factory=lambda: list(DEFAULT_IT_CRAWL_TERMS))
    listing_page_limit: int = 0
    max_results_per_site: int = 8
    request_timeout_seconds: int = 20
    fetch_details: bool = True
    store_html: bool = False
    detail_refetch_hours: int = 24
    concurrency: int = 4
    pause_between_searches_seconds: float = 1.0
    ai_enrichment_enabled: bool = False
    ai_provider: str = "heuristic"
    ai_model: str = ""
    user_agent: str = DEFAULT_USER_AGENT


@dataclass
class CriteriaConfig:
    roles: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    experience_levels: list[str] = field(default_factory=list)
    education_levels: list[str] = field(default_factory=list)
    employment_types: list[str] = field(default_factory=list)
    required_terms: list[str] = field(default_factory=list)
    extra_terms: list[str] = field(default_factory=lambda: list(DEFAULT_EXTRA_TERMS))
    strict_match_groups: list[str] = field(default_factory=list)


@dataclass
class ScheduleConfig:
    enabled: bool = False
    timezone: str = "Asia/Seoul"
    mode: str = "fixed_times"
    times: list[str] = field(default_factory=lambda: ["09:00"])
    interval_hours: int = 4
    run_on_start: bool = True
    max_runs: int | None = None


@dataclass
class AppConfig:
    output_dir: Path
    search: SearchConfig = field(default_factory=SearchConfig)
    criteria: CriteriaConfig = field(default_factory=CriteriaConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    config_source: str = "runtime"


def _ensure_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise TypeError(f"Expected list, got {type(value).__name__}")


def _build_search_config(raw: dict[str, Any]) -> SearchConfig:
    crawl_strategy = str(raw.get("crawl_strategy", "broad_it_scan")).strip() or "broad_it_scan"
    if crawl_strategy not in {"broad_it_scan", "query_search"}:
        raise ValueError("search.crawl_strategy must be 'broad_it_scan' or 'query_search'")

    ai_provider = str(raw.get("ai_provider", "heuristic")).strip() or "heuristic"
    if ai_provider not in {"heuristic", "openai"}:
        raise ValueError("search.ai_provider must be 'heuristic' or 'openai'")

    return SearchConfig(
        sites=_ensure_list(raw.get("sites")) or list(DEFAULT_SITE_KEYS),
        queries=_ensure_list(raw.get("queries")),
        crawl_strategy=crawl_strategy,
        crawl_terms=_ensure_list(raw.get("crawl_terms")) or list(DEFAULT_IT_CRAWL_TERMS),
        listing_page_limit=max(0, int(raw.get("listing_page_limit", 0))),
        max_results_per_site=max(1, int(raw.get("max_results_per_site", 8))),
        request_timeout_seconds=max(5, int(raw.get("request_timeout_seconds", 20))),
        fetch_details=bool(raw.get("fetch_details", True)),
        store_html=bool(raw.get("store_html", False)),
        detail_refetch_hours=max(1, int(raw.get("detail_refetch_hours", 24))),
        concurrency=max(1, int(raw.get("concurrency", 4))),
        pause_between_searches_seconds=max(
            0.0, float(raw.get("pause_between_searches_seconds", 1.0))
        ),
        ai_enrichment_enabled=bool(raw.get("ai_enrichment_enabled", False)),
        ai_provider=ai_provider,
        ai_model=str(raw.get("ai_model", "")).strip(),
        user_agent=str(raw.get("user_agent", DEFAULT_USER_AGENT)).strip() or DEFAULT_USER_AGENT,
    )


def _build_criteria_config(raw: dict[str, Any]) -> CriteriaConfig:
    return CriteriaConfig(
        roles=_ensure_list(raw.get("roles")),
        keywords=_ensure_list(raw.get("keywords")),
        exclude_keywords=_ensure_list(raw.get("exclude_keywords")),
        locations=_ensure_list(raw.get("locations")),
        companies=_ensure_list(raw.get("companies")),
        experience_levels=_ensure_list(raw.get("experience_levels")),
        education_levels=_ensure_list(raw.get("education_levels")),
        employment_types=_ensure_list(raw.get("employment_types")),
        required_terms=_ensure_list(raw.get("required_terms")),
        extra_terms=_ensure_list(raw.get("extra_terms")) or list(DEFAULT_EXTRA_TERMS),
        strict_match_groups=_ensure_list(raw.get("strict_match_groups")),
    )


def _build_schedule_config(raw: dict[str, Any]) -> ScheduleConfig:
    interval_hours = raw.get("interval_hours")
    if interval_hours in (None, "") and raw.get("interval_minutes") not in (None, ""):
        interval_hours = max(1, int(raw["interval_minutes"]) // 60)

    schedule = ScheduleConfig(
        enabled=bool(raw.get("enabled", False)),
        timezone=str(raw.get("timezone", "Asia/Seoul")).strip() or "Asia/Seoul",
        mode=str(raw.get("mode", "fixed_times")).strip() or "fixed_times",
        times=_ensure_list(raw.get("times")) or ["09:00"],
        interval_hours=max(1, int(interval_hours or 4)),
        run_on_start=bool(raw.get("run_on_start", True)),
        max_runs=int(raw["max_runs"]) if raw.get("max_runs") not in (None, "") else None,
    )
    if schedule.mode not in {"fixed_times", "interval_hours"}:
        raise ValueError("schedule.mode must be 'fixed_times' or 'interval_hours'")
    return schedule


def build_config(
    raw: dict[str, Any] | None,
    *,
    base_dir: str | Path | None = None,
    source: str = "runtime",
) -> AppConfig:
    payload = raw or {}
    root_dir = Path(base_dir or ".").resolve()
    output_dir = payload.get("output_dir") or "./data/exports"
    search_raw = payload.get("search", {})
    criteria_raw = payload.get("criteria", {})
    schedule_raw = payload.get("schedule", {})
    return AppConfig(
        output_dir=(root_dir / str(output_dir)).resolve(),
        search=_build_search_config(search_raw),
        criteria=_build_criteria_config(criteria_raw),
        schedule=_build_schedule_config(schedule_raw),
        config_source=source,
    )


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return build_config(raw, base_dir=config_path.parent, source=f"file:{config_path}")


def config_to_dict(config: AppConfig) -> dict[str, Any]:
    return {
        "output_dir": str(config.output_dir),
        "search": {
            "sites": list(config.search.sites),
            "queries": list(config.search.queries),
            "crawl_strategy": config.search.crawl_strategy,
            "crawl_terms": list(config.search.crawl_terms),
            "listing_page_limit": config.search.listing_page_limit,
            "max_results_per_site": config.search.max_results_per_site,
            "request_timeout_seconds": config.search.request_timeout_seconds,
            "fetch_details": config.search.fetch_details,
            "store_html": config.search.store_html,
            "detail_refetch_hours": config.search.detail_refetch_hours,
            "concurrency": config.search.concurrency,
            "pause_between_searches_seconds": config.search.pause_between_searches_seconds,
            "ai_enrichment_enabled": config.search.ai_enrichment_enabled,
            "ai_provider": config.search.ai_provider,
            "ai_model": config.search.ai_model,
            "user_agent": config.search.user_agent,
        },
        "criteria": {
            "roles": list(config.criteria.roles),
            "keywords": list(config.criteria.keywords),
            "exclude_keywords": list(config.criteria.exclude_keywords),
            "locations": list(config.criteria.locations),
            "companies": list(config.criteria.companies),
            "experience_levels": list(config.criteria.experience_levels),
            "education_levels": list(config.criteria.education_levels),
            "employment_types": list(config.criteria.employment_types),
            "required_terms": list(config.criteria.required_terms),
            "extra_terms": list(config.criteria.extra_terms),
            "strict_match_groups": list(config.criteria.strict_match_groups),
        },
        "schedule": {
            "enabled": config.schedule.enabled,
            "timezone": config.schedule.timezone,
            "mode": config.schedule.mode,
            "times": list(config.schedule.times),
            "interval_hours": config.schedule.interval_hours,
            "run_on_start": config.schedule.run_on_start,
            "max_runs": config.schedule.max_runs,
        },
    }


def dump_config(path: str | Path, config: AppConfig) -> None:
    config_path = Path(path).expanduser().resolve()
    payload = config_to_dict(config)
    config_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def build_queries(criteria: CriteriaConfig, manual_queries: list[str]) -> list[str]:
    if manual_queries:
        return _dedupe([query for query in manual_queries if query.strip()])

    shared_terms = _dedupe(
        criteria.keywords
        + criteria.locations
        + criteria.companies
        + criteria.experience_levels
        + criteria.education_levels
        + criteria.employment_types
        + criteria.extra_terms
    )

    seeds = criteria.roles or criteria.required_terms or ["채용 공고"]
    queries = []
    for seed in seeds:
        queries.append(" ".join([seed, *shared_terms]).strip())
    return _dedupe(queries)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        cleaned = " ".join(value.split())
        if not cleaned:
            continue
        marker = cleaned.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(cleaned)
    return unique
