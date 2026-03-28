from __future__ import annotations

from job_harvest.models import SiteDefinition


DEFAULT_SITES: dict[str, SiteDefinition] = {
    "saramin": SiteDefinition("saramin", "Saramin", "saramin.co.kr"),
    "jobkorea": SiteDefinition("jobkorea", "JobKorea", "jobkorea.co.kr"),
    "linkedin": SiteDefinition("linkedin", "LinkedIn", "linkedin.com"),
    "jobplanet": SiteDefinition("jobplanet", "JobPlanet", "jobplanet.co.kr"),
    "jumpit": SiteDefinition("jumpit", "Jumpit", "jumpit.saramin.co.kr"),
    "wanted": SiteDefinition("wanted", "Wanted", "wanted.co.kr"),
    "rocketpunch": SiteDefinition("rocketpunch", "RocketPunch", "rocketpunch.com"),
    "remember": SiteDefinition("remember", "Remember", "rememberapp.co.kr"),
    "blind": SiteDefinition("blind", "Blind", "teamblind.com"),
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
