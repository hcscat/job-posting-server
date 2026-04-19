from __future__ import annotations

from dataclasses import dataclass

from job_harvest.config import CRITERIA_FILTER_FIELDS, CriteriaConfig, STRICT_MATCHABLE_FIELDS
from job_harvest.filter_taxonomy import get_site_filter_support


PRIMARY_QUERY_FIELDS = (
    "roles",
    "keywords",
    "skills",
    "industries",
    "tags",
    "companies",
    "theme_tags",
    "position_levels",
)

SECONDARY_QUERY_FIELDS = (
    "locations",
    "experience_levels",
    "education_levels",
    "employment_types",
    "workplace_types",
    "company_types",
    "company_sizes",
    "salary_ranges",
    "majors",
    "certifications",
    "preferred_conditions",
    "welfare",
    "date_posted",
    "deadline",
    "easy_apply",
    "applicant_signals",
    "network_signals",
    "leader_positions",
    "headhunting",
)

TEXT_QUERY_COMPATIBLE_FIELDS = (
    "roles",
    "keywords",
    "companies",
    "locations",
    "experience_levels",
    "education_levels",
    "employment_types",
    "industries",
    "position_levels",
    "preferred_conditions",
    "skills",
    "tags",
    "workplace_types",
    "theme_tags",
)


@dataclass(frozen=True)
class SiteQueryPlan:
    site_key: str
    supported_fields: tuple[str, ...]
    active_fields: tuple[str, ...]
    queries: tuple[str, ...]
    location_hint: str | None


def normalize_terms(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        cleaned = " ".join(str(value).split())
        if not cleaned:
            continue
        marker = cleaned.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(cleaned)
    return unique


def get_supported_filter_fields(site_key: str) -> tuple[str, ...]:
    fields = [
        capability.standardized_field
        for capability in get_site_filter_support(site_key)
        if capability.standardized_field in CRITERIA_FILTER_FIELDS
    ]
    return tuple(normalize_terms(fields))


def get_queryable_filter_fields(site_key: str) -> tuple[str, ...]:
    _ = site_key
    return tuple(TEXT_QUERY_COMPATIBLE_FIELDS)


def get_criteria_values(criteria: CriteriaConfig, field_name: str) -> list[str]:
    raw_values = getattr(criteria, field_name, [])
    if not isinstance(raw_values, list):
        return []
    return normalize_terms([str(value) for value in raw_values])


def get_active_filter_fields(criteria: CriteriaConfig) -> tuple[str, ...]:
    return tuple(
        field_name
        for field_name in STRICT_MATCHABLE_FIELDS
        if get_criteria_values(criteria, field_name)
    )


def has_active_filters(criteria: CriteriaConfig) -> bool:
    if get_active_filter_fields(criteria):
        return True
    return bool(get_criteria_values(criteria, "required_terms") or get_criteria_values(criteria, "exclude_keywords"))


def build_site_query_plan(
    *,
    site_key: str,
    criteria: CriteriaConfig,
    crawl_strategy: str,
    crawl_terms: list[str],
    manual_queries: list[str],
) -> SiteQueryPlan:
    supported_fields = get_supported_filter_fields(site_key)
    queryable_fields = get_queryable_filter_fields(site_key)
    active_fields = tuple(
        field_name for field_name in supported_fields if get_criteria_values(criteria, field_name)
    )
    fallback_terms = [] if crawl_strategy == "query_search" and manual_queries else crawl_terms
    generated_queries = build_site_queries(
        criteria=criteria,
        fallback_terms=fallback_terms,
        queryable_fields=queryable_fields,
    )

    if crawl_strategy == "query_search" and manual_queries:
        queries = tuple(normalize_terms(list(manual_queries) + generated_queries))
    elif crawl_strategy == "broad_it_scan" and not has_active_filters(criteria):
        queries = tuple(normalize_terms(list(crawl_terms)))
    else:
        queries = tuple(generated_queries)

    location_hint = None
    if "locations" in queryable_fields:
        locations = get_criteria_values(criteria, "locations")
        location_hint = locations[0] if locations else None

    return SiteQueryPlan(
        site_key=site_key,
        supported_fields=supported_fields,
        active_fields=active_fields,
        queries=queries or tuple(normalize_terms(list(crawl_terms))),
        location_hint=location_hint,
    )


def build_site_queries(
    *,
    criteria: CriteriaConfig,
    fallback_terms: list[str],
    queryable_fields: tuple[str, ...],
) -> list[str]:
    supported_fields = set(queryable_fields)
    primary_terms = _collect_terms(criteria, PRIMARY_QUERY_FIELDS, supported_fields)
    secondary_terms = _collect_terms(criteria, SECONDARY_QUERY_FIELDS, supported_fields)
    required_terms = get_criteria_values(criteria, "required_terms")
    fallback = normalize_terms(list(fallback_terms))

    if not primary_terms and not secondary_terms and not required_terms and not fallback:
        return []

    if not primary_terms:
        primary_terms = fallback or secondary_terms[:]
    if not primary_terms:
        primary_terms = ["job"]

    queries: list[str] = []
    for seed in primary_terms[:8]:
        suffix = [
            term
            for term in normalize_terms(secondary_terms + required_terms)
            if term.casefold() != seed.casefold()
        ]
        if suffix:
            queries.append(" ".join([seed, *suffix[:4]]).strip())
        queries.append(seed)

    if not queries and fallback:
        queries.extend(fallback)
    return normalize_terms(queries)[:12]


def _collect_terms(
    criteria: CriteriaConfig,
    field_names: tuple[str, ...],
    supported_fields: set[str],
) -> list[str]:
    terms: list[str] = []
    for field_name in field_names:
        if field_name not in supported_fields:
            continue
        terms.extend(get_criteria_values(criteria, field_name))
    return normalize_terms(terms)
