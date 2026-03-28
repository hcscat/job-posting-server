from __future__ import annotations

from job_harvest.models import SiteDefinition


DEFAULT_SITES: dict[str, SiteDefinition] = {
    "saramin": SiteDefinition("saramin", "사람인", "saramin.co.kr"),
    "jobkorea": SiteDefinition("jobkorea", "잡코리아", "jobkorea.co.kr"),
    "linkedin": SiteDefinition("linkedin", "LinkedIn", "linkedin.com"),
    "jobplanet": SiteDefinition("jobplanet", "잡플래닛", "jobplanet.co.kr"),
    "jumpit": SiteDefinition("jumpit", "점핏", "jumpit.saramin.co.kr"),
    "wanted": SiteDefinition("wanted", "원티드", "wanted.co.kr"),
    "rocketpunch": SiteDefinition("rocketpunch", "로켓펀치", "rocketpunch.com"),
    "remember": SiteDefinition("remember", "리멤버", "rememberapp.co.kr"),
    "blind": SiteDefinition("blind", "블라인드", "teamblind.com"),
}

STABLE_SITE_KEYS = {
    "saramin",
    "jobkorea",
    "linkedin",
    "wanted",
    "jumpit",
    "remember",
}

BEST_EFFORT_SITE_KEYS = set(DEFAULT_SITES) - STABLE_SITE_KEYS


def resolve_sites(site_keys: list[str]) -> list[SiteDefinition]:
    sites: list[SiteDefinition] = []
    for key in site_keys:
        normalized = key.strip().lower()
        if normalized not in DEFAULT_SITES:
            raise ValueError(
                f"Unknown site '{key}'. Available sites: {', '.join(sorted(DEFAULT_SITES))}"
            )
        sites.append(DEFAULT_SITES[normalized])
    return sites
