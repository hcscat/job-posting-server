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

SITE_LABELS: dict[str, dict[str, str]] = {
    "ko": {
        "saramin": "사람인",
        "jobkorea": "잡코리아",
        "linkedin": "링크드인",
        "jobplanet": "잡플래닛",
        "jumpit": "점핏",
        "wanted": "원티드",
        "rocketpunch": "로켓펀치",
        "remember": "리멤버",
        "blind": "블라인드",
    },
    "en": {
        "saramin": "Saramin",
        "jobkorea": "JobKorea",
        "linkedin": "LinkedIn",
        "jobplanet": "JobPlanet",
        "jumpit": "Jumpit",
        "wanted": "Wanted",
        "rocketpunch": "RocketPunch",
        "remember": "Remember",
        "blind": "Blind",
    },
}

SITE_LABELS = {
    "ko": {
        "saramin": "\uc0ac\ub78c\uc778",
        "jobkorea": "\uc7a1\ucf54\ub9ac\uc544",
        "linkedin": "\ub9c1\ud06c\ub4dc\uc778",
        "jobplanet": "\uc7a1\ud50c\ub798\ub2db",
        "jumpit": "\uc810\ud54f",
        "wanted": "\uc6d0\ud2f0\ub4dc",
        "rocketpunch": "\ub85c\ucf13\ud380\uce58",
        "remember": "\ub9ac\uba64\ubc84",
        "blind": "\ube14\ub77c\uc778\ub4dc",
    },
    "en": {
        "saramin": "Saramin",
        "jobkorea": "JobKorea",
        "linkedin": "LinkedIn",
        "jobplanet": "JobPlanet",
        "jumpit": "Jumpit",
        "wanted": "Wanted",
        "rocketpunch": "RocketPunch",
        "remember": "Remember",
        "blind": "Blind",
    },
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


def get_site_label(site_key: str, locale: str, fallback: str = "") -> str:
    labels = SITE_LABELS.get(locale) or SITE_LABELS["en"]
    return labels.get(site_key, fallback or DEFAULT_SITES.get(site_key, SiteDefinition(site_key, site_key, "")).name)
