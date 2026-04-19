from __future__ import annotations

from dataclasses import dataclass

from job_harvest.sites import DEFAULT_SITES


@dataclass(frozen=True)
class StandardFilterField:
    key: str
    stage: str
    summary: str


@dataclass(frozen=True)
class SiteFilterCapability:
    native_filter: str
    standardized_field: str
    evidence: str
    notes: str = ""


CURRENT_STANDARD_FILTER_FIELDS: tuple[StandardFilterField, ...] = (
    StandardFilterField("roles", "current", "Role, discipline, job family, or title keywords."),
    StandardFilterField("keywords", "current", "Free-text keywords, technologies, or domain terms."),
    StandardFilterField("locations", "current", "Region, city, district, or remote-location scope."),
    StandardFilterField("companies", "current", "Company name filters."),
    StandardFilterField("experience_levels", "current", "Seniority or years-of-experience filters."),
    StandardFilterField("education_levels", "current", "Education requirements."),
    StandardFilterField("employment_types", "current", "Employment or contract type."),
    StandardFilterField("required_terms", "current", "Terms that must appear in the posting."),
    StandardFilterField("exclude_keywords", "current", "Terms that should be excluded."),
)

RECOMMENDED_STANDARD_FILTER_FIELDS: tuple[StandardFilterField, ...] = (
    StandardFilterField("industries", "future", "Industry, business domain, or employer sector."),
    StandardFilterField("salary_ranges", "future", "Salary or compensation range."),
    StandardFilterField("company_types", "future", "Listed company, startup, public sector, and similar types."),
    StandardFilterField("company_sizes", "future", "Employer size bands."),
    StandardFilterField("position_levels", "future", "Position level, title band, or org level."),
    StandardFilterField("majors", "future", "Major or field-of-study requirements."),
    StandardFilterField("certifications", "future", "Certificates or licenses."),
    StandardFilterField("preferred_conditions", "future", "Preferred qualifications and applicant conditions."),
    StandardFilterField("welfare", "future", "Benefits and welfare filters."),
    StandardFilterField("skills", "future", "Structured skills or tech stack filters."),
    StandardFilterField("tags", "future", "Site-specific labels or thematic tags."),
    StandardFilterField("workplace_types", "future", "Remote, hybrid, or on-site work mode."),
    StandardFilterField("date_posted", "future", "Posted date or freshness filter."),
    StandardFilterField("deadline", "future", "Application deadline filter."),
    StandardFilterField("easy_apply", "future", "Native one-click or easy-apply filter."),
    StandardFilterField("applicant_signals", "future", "Applicant volume or competition signals."),
    StandardFilterField("network_signals", "future", "Social-graph or network proximity signals."),
    StandardFilterField("leader_positions", "future", "Leader-only or executive-only filter."),
    StandardFilterField("headhunting", "future", "Headhunting-posting inclusion or exclusion."),
    StandardFilterField("theme_tags", "future", "Editorial themes such as hiring drive or AI company tags."),
)

ALL_STANDARD_FILTER_FIELDS = {
    field.key: field for field in CURRENT_STANDARD_FILTER_FIELDS + RECOMMENDED_STANDARD_FILTER_FIELDS
}


SITE_FILTER_SUPPORT: dict[str, tuple[SiteFilterCapability, ...]] = {
    "saramin": (
        SiteFilterCapability("keywords", "keywords", "official_api"),
        SiteFilterCapability("region", "locations", "official_api", "loc_cd, loc_mcd, loc_bcd"),
        SiteFilterCapability("industry", "industries", "official_api", "ind_cd"),
        SiteFilterCapability("job group", "roles", "official_api", "job_mid_cd, job_cd"),
        SiteFilterCapability("employment type", "employment_types", "official_api", "job_type"),
        SiteFilterCapability("education", "education_levels", "official_api", "edu_lv"),
        SiteFilterCapability("listed-company status", "company_types", "official_api", "stock"),
        SiteFilterCapability("posted / updated date", "date_posted", "official_api"),
        SiteFilterCapability("deadline", "deadline", "official_api"),
        SiteFilterCapability("exclude headhunters", "headhunting", "official_api", "sr=directhire"),
        SiteFilterCapability("sort order", "date_posted", "official_api", "Sort is available but not yet standardized."),
    ),
    "jobkorea": (
        SiteFilterCapability("role / job family", "roles", "public_ui"),
        SiteFilterCapability("region", "locations", "public_ui"),
        SiteFilterCapability("industry", "industries", "public_ui"),
        SiteFilterCapability("employment type", "employment_types", "public_ui"),
        SiteFilterCapability("position level / title / pay", "position_levels", "public_ui"),
        SiteFilterCapability("education", "education_levels", "public_ui"),
        SiteFilterCapability("major", "majors", "public_ui"),
        SiteFilterCapability("certification", "certifications", "public_ui"),
        SiteFilterCapability("preferred conditions", "preferred_conditions", "public_ui"),
        SiteFilterCapability("welfare", "welfare", "public_ui"),
        SiteFilterCapability("company track", "company_types", "public_ui", "Large company, foreign company, public sector, listed, and similar."),
    ),
    "linkedin": (
        SiteFilterCapability("location", "locations", "official_help"),
        SiteFilterCapability("date posted", "date_posted", "official_help"),
        SiteFilterCapability("easy apply", "easy_apply", "official_help"),
        SiteFilterCapability("company", "companies", "official_help"),
        SiteFilterCapability("experience level", "experience_levels", "official_help"),
        SiteFilterCapability("employment type", "employment_types", "official_help"),
        SiteFilterCapability("under 10 applicants", "applicant_signals", "official_help"),
        SiteFilterCapability("in your network", "network_signals", "official_help"),
    ),
    "jumpit": (
        SiteFilterCapability("tech stack", "skills", "public_ui"),
        SiteFilterCapability("experience", "experience_levels", "public_ui"),
        SiteFilterCapability("region", "locations", "public_ui"),
        SiteFilterCapability("tags", "tags", "public_ui"),
    ),
    "wanted": (
        SiteFilterCapability("remote-work theme", "workplace_types", "public_home"),
        SiteFilterCapability("contract theme", "employment_types", "public_home"),
        SiteFilterCapability("intern theme", "employment_types", "public_home"),
        SiteFilterCapability("actively hiring theme", "theme_tags", "public_home"),
        SiteFilterCapability("large hiring drive theme", "theme_tags", "public_home"),
        SiteFilterCapability("ai company theme", "theme_tags", "public_home"),
        SiteFilterCapability("foreign-language friendly theme", "preferred_conditions", "public_home"),
        SiteFilterCapability("company growth / size themes", "company_sizes", "public_home"),
        SiteFilterCapability("investment / retention / bonus themes", "theme_tags", "public_home"),
    ),
    "rocketpunch": (
        SiteFilterCapability("job group", "roles", "marketing_pdf"),
        SiteFilterCapability("industry", "industries", "marketing_pdf"),
        SiteFilterCapability("hiring conditions", "employment_types", "marketing_pdf", "Documented generically, not enumerated publicly."),
        SiteFilterCapability("specialized domain", "tags", "marketing_pdf", "Documented as professional field / specialization."),
        SiteFilterCapability("seniority", "experience_levels", "public_snippet"),
        SiteFilterCapability("employment type", "employment_types", "public_snippet"),
        SiteFilterCapability("work type", "workplace_types", "public_snippet"),
    ),
    "remember": (
        SiteFilterCapability("role", "roles", "public_ui"),
        SiteFilterCapability("salary", "salary_ranges", "public_ui"),
        SiteFilterCapability("region", "locations", "public_ui"),
        SiteFilterCapability("experience", "experience_levels", "public_ui"),
        SiteFilterCapability("company type", "company_types", "public_ui"),
        SiteFilterCapability("industry", "industries", "public_ui"),
        SiteFilterCapability("leader-only toggle", "leader_positions", "public_ui"),
        SiteFilterCapability("headhunting toggle", "headhunting", "public_ui"),
        SiteFilterCapability("quick-apply toggle", "easy_apply", "public_ui"),
        SiteFilterCapability("active-hiring toggle", "theme_tags", "public_ui"),
    ),
    "jobplanet": (
        SiteFilterCapability("open recruitment", "theme_tags", "public_ui"),
        SiteFilterCapability("experience", "experience_levels", "public_ui"),
        SiteFilterCapability("region", "locations", "public_ui"),
        SiteFilterCapability("employment type", "employment_types", "public_ui"),
        SiteFilterCapability("education", "education_levels", "public_ui"),
        SiteFilterCapability("industry category", "industries", "public_ui"),
    ),
    "blind": (
        SiteFilterCapability("search by title or company", "keywords", "public_snippet"),
        SiteFilterCapability("date posted", "date_posted", "public_snippet"),
        SiteFilterCapability("location", "locations", "public_snippet"),
        SiteFilterCapability("remote only", "workplace_types", "public_snippet"),
        SiteFilterCapability("required experience", "experience_levels", "public_snippet"),
        SiteFilterCapability("salary", "salary_ranges", "public_snippet"),
        SiteFilterCapability("company size", "company_sizes", "public_snippet"),
        SiteFilterCapability("company technologies", "skills", "public_snippet"),
    ),
}


def get_site_filter_support(site_key: str) -> tuple[SiteFilterCapability, ...]:
    normalized = site_key.strip().lower()
    if normalized not in SITE_FILTER_SUPPORT:
        raise ValueError(
            f"Unknown site '{site_key}'. Available sites: {', '.join(sorted(SITE_FILTER_SUPPORT))}"
        )
    return SITE_FILTER_SUPPORT[normalized]


def get_uncovered_sites() -> set[str]:
    return set(DEFAULT_SITES) - set(SITE_FILTER_SUPPORT)
