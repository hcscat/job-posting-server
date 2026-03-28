from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from job_harvest.schemas import SettingsPayload
from job_harvest.sites import DEFAULT_SITES


DEFAULT_REQUEST_MODEL = "gpt-4.1-mini"

SITE_ALIASES = {
    "saramin": ("saramin", "사람인"),
    "jobkorea": ("jobkorea", "잡코리아"),
    "linkedin": ("linkedin", "linked in", "링크드인"),
    "jobplanet": ("jobplanet", "잡플래닛"),
    "jumpit": ("jumpit", "점핏"),
    "wanted": ("wanted", "원티드"),
    "rocketpunch": ("rocketpunch", "로켓펀치"),
    "remember": ("remember", "리멤버"),
    "blind": ("blind", "teamblind", "블라인드"),
}

ROLE_HINTS = (
    "frontend",
    "backend",
    "fullstack",
    "software engineer",
    "data engineer",
    "data scientist",
    "machine learning engineer",
    "devops engineer",
    "security engineer",
    "mobile engineer",
    "ios engineer",
    "android engineer",
    "qa engineer",
    "sre",
    "platform engineer",
    "product manager",
    "프론트엔드",
    "프론트엔드 개발",
    "프론트엔드 개발자",
    "백엔드",
    "백엔드 개발",
    "백엔드 개발자",
    "풀스택",
    "소프트웨어 엔지니어",
    "데이터 엔지니어",
    "데이터 사이언티스트",
    "머신러닝 엔지니어",
    "개발자",
    "개발",
    "데브옵스",
    "보안 엔지니어",
    "모바일 개발자",
    "iOS 개발자",
    "안드로이드 개발자",
    "QA 엔지니어",
    "플랫폼 엔지니어",
    "프로덕트 매니저",
)

KEYWORD_HINTS = (
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "vue",
    "angular",
    "node",
    "node.js",
    "spring",
    "django",
    "flask",
    "fastapi",
    "kotlin",
    "swift",
    "ios",
    "android",
    "aws",
    "gcp",
    "azure",
    "docker",
    "kubernetes",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "llm",
    "ai",
    "ml",
    "머신러닝",
    "딥러닝",
)

LOCATION_HINTS = (
    "seoul",
    "pangyo",
    "bundang",
    "suwon",
    "daejeon",
    "busan",
    "incheon",
    "remote",
    "hybrid",
    "서울",
    "판교",
    "분당",
    "수원",
    "대전",
    "부산",
    "인천",
    "원격",
    "재택",
    "하이브리드",
)

EDUCATION_HINTS = (
    "고졸",
    "초대졸",
    "대졸",
    "학사",
    "석사",
    "박사",
    "무관",
    "bachelor",
    "master",
    "phd",
)

EMPLOYMENT_HINTS = (
    "정규직",
    "계약직",
    "인턴",
    "프리랜서",
    "파견",
    "full-time",
    "contract",
    "intern",
    "freelance",
)

FIELD_MARKERS = {
    "roles": ("직무", "포지션", "role", "roles"),
    "keywords": ("기술", "스킬", "키워드", "tech", "stack", "keyword", "keywords"),
    "locations": ("지역", "근무지", "location", "locations"),
    "companies": ("회사", "기업", "company", "companies"),
    "experience_levels": ("경력", "experience"),
    "education_levels": ("학력", "education"),
    "employment_types": ("고용형태", "근무형태", "employment", "employment type"),
    "required_terms": ("필수", "반드시 포함", "must include", "required"),
    "exclude_keywords": ("제외", "빼고", "without", "exclude"),
}

EXPERIENCE_REGEXES = (
    re.compile(r"(신입|경력무관|인턴|주니어|시니어)"),
    re.compile(r"(\d+\+?\s*년(?:\s*(?:이상|이하))?)"),
    re.compile(r"\b(entry level|junior|senior|mid-level)\b", re.IGNORECASE),
)

STRICT_PATTERNS = ("만", "만으로", "정확히", "반드시", "only", "exactly", "strict")
BROAD_PATTERNS = (
    "모든 공고",
    "전체 공고",
    "전부",
    "전체 수집",
    "모두 수집",
    "all jobs",
    "all postings",
)

ALL_MARKERS = tuple(marker for markers in FIELD_MARKERS.values() for marker in markers)


@dataclass
class RequestInterpretation:
    provider: str
    model: str
    notes: list[str]
    payload: SettingsPayload


def interpret_collection_request(text: str, current_payload: SettingsPayload) -> RequestInterpretation:
    cleaned = " ".join(text.split())
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            return _interpret_with_openai(cleaned, current_payload, api_key)
        except Exception:
            pass
    return _interpret_with_heuristics(cleaned, current_payload)


def _interpret_with_openai(
    text: str,
    current_payload: SettingsPayload,
    api_key: str,
) -> RequestInterpretation:
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=DEFAULT_REQUEST_MODEL,
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Convert a natural-language job collection request into JSON overrides for an existing "
                            "settings object. Return strict JSON with keys: updates, notes. "
                            "updates may contain only these keys: site_keys, crawl_strategy, crawl_terms, queries, "
                            "roles, keywords, exclude_keywords, locations, companies, experience_levels, "
                            "education_levels, employment_types, required_terms, strict_match_groups. "
                            "Values must be strings or arrays of strings. Keep values concise."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "\n\n".join(
                            [
                                f"Current settings: {json.dumps(current_payload.model_dump(), ensure_ascii=False)}",
                                f"User request: {text}",
                            ]
                        ),
                    }
                ],
            },
        ],
    )
    payload = json.loads(response.output_text)
    notes = [str(item).strip() for item in payload.get("notes", []) if str(item).strip()]
    merged = _merge_payload(current_payload, _sanitize_updates(payload.get("updates") or {}))
    return RequestInterpretation(
        provider="openai",
        model=DEFAULT_REQUEST_MODEL,
        notes=notes or ["Applied OpenAI request interpretation."],
        payload=merged,
    )


def _interpret_with_heuristics(text: str, current_payload: SettingsPayload) -> RequestInterpretation:
    lowered = text.casefold()
    updates: dict[str, object] = {}
    notes = ["Applied heuristic request interpretation."]

    if _contains_any(lowered, ("모든 사이트", "전체 사이트", "all sites")):
        updates["site_keys"] = list(DEFAULT_SITES)
    else:
        site_keys = _extract_sites(lowered)
        if site_keys:
            updates["site_keys"] = site_keys

    roles = _dedupe(_extract_catalog_matches(text, lowered, ROLE_HINTS) + _extract_field_values(text, "roles"))
    keywords = _dedupe(_extract_catalog_matches(text, lowered, KEYWORD_HINTS) + _extract_field_values(text, "keywords"))
    locations = _dedupe(_extract_catalog_matches(text, lowered, LOCATION_HINTS) + _extract_field_values(text, "locations"))
    companies = _extract_field_values(text, "companies")
    education_levels = _dedupe(
        _extract_catalog_matches(text, lowered, EDUCATION_HINTS) + _extract_field_values(text, "education_levels")
    )
    employment_types = _dedupe(
        _extract_catalog_matches(text, lowered, EMPLOYMENT_HINTS) + _extract_field_values(text, "employment_types")
    )
    experience_levels = _dedupe(_extract_experience_levels(text) + _extract_field_values(text, "experience_levels"))
    required_terms = _extract_field_values(text, "required_terms")
    exclude_keywords = _extract_field_values(text, "exclude_keywords")

    if roles:
        updates["roles"] = roles
    if keywords:
        updates["keywords"] = keywords
    if locations:
        updates["locations"] = locations
    if companies:
        updates["companies"] = companies
    if education_levels:
        updates["education_levels"] = education_levels
    if employment_types:
        updates["employment_types"] = employment_types
    if experience_levels:
        updates["experience_levels"] = experience_levels
    if required_terms:
        updates["required_terms"] = required_terms
    if exclude_keywords:
        updates["exclude_keywords"] = exclude_keywords

    strict_match_groups: list[str] = []
    if _contains_any(lowered, STRICT_PATTERNS):
        if roles:
            strict_match_groups.append("roles")
        if locations:
            strict_match_groups.append("locations")
        if companies:
            strict_match_groups.append("companies")
    if strict_match_groups:
        updates["strict_match_groups"] = strict_match_groups

    if _contains_any(lowered, BROAD_PATTERNS):
        updates["crawl_strategy"] = "broad_it_scan"
        crawl_terms = _dedupe(roles + keywords)
        if crawl_terms:
            updates["crawl_terms"] = crawl_terms
    else:
        updates["crawl_strategy"] = "query_search"
        queries = _build_queries_from_updates(
            roles=roles,
            keywords=keywords,
            locations=locations,
            companies=companies,
            experience_levels=experience_levels,
        )
        updates["queries"] = queries or [text]

    merged = _merge_payload(current_payload, _sanitize_updates(updates))
    return RequestInterpretation(
        provider="heuristic",
        model="local-heuristic",
        notes=notes,
        payload=merged,
    )


def _extract_sites(lowered: str) -> list[str]:
    detected: list[str] = []
    for site_key, aliases in SITE_ALIASES.items():
        if any(alias.casefold() in lowered for alias in aliases):
            detected.append(site_key)
    return detected


def _extract_catalog_matches(original: str, lowered: str, hints: tuple[str, ...]) -> list[str]:
    matched: list[str] = []
    for hint in hints:
        if hint.casefold() in lowered:
            matched.append(_restore_case(original, hint))
    return matched


def _restore_case(original: str, token: str) -> str:
    pattern = re.compile(re.escape(token), re.IGNORECASE)
    match = pattern.search(original)
    return match.group(0) if match else token


def _extract_field_values(text: str, field_name: str) -> list[str]:
    markers = FIELD_MARKERS[field_name]
    marker_pattern = "|".join(re.escape(marker) for marker in markers)
    lookahead_pattern = "|".join(re.escape(marker) for marker in ALL_MARKERS)
    pattern = re.compile(
        rf"(?:{marker_pattern})\s*(?:은|는|이|가|으로|:|=)?\s*(.+?)(?=(?:{lookahead_pattern})\s*(?:은|는|이|가|으로|:|=)|[.!?\n]|$)",
        re.IGNORECASE,
    )
    values: list[str] = []
    for match in pattern.finditer(text):
        values.extend(_split_items(match.group(1)))
    return _dedupe(values)


def _extract_experience_levels(text: str) -> list[str]:
    values: list[str] = []
    for pattern in EXPERIENCE_REGEXES:
        values.extend(match.group(1) for match in pattern.finditer(text))
    return _dedupe(values)


def _build_queries_from_updates(
    *,
    roles: list[str],
    keywords: list[str],
    locations: list[str],
    companies: list[str],
    experience_levels: list[str],
) -> list[str]:
    seeds = roles or keywords or companies
    suffix = locations + experience_levels
    queries: list[str] = []
    for seed in seeds[:6]:
        parts = [seed, *suffix[:4]]
        query = " ".join(part for part in parts if part).strip()
        if query:
            queries.append(query)
    return _dedupe(queries)


def _split_items(text: str) -> list[str]:
    cleaned = re.sub(r"^[=:,\s]+", "", text.strip())
    if not cleaned:
        return []
    parts = re.split(r",|/|\||\b(?:and|or)\b|그리고|또는|및", cleaned)
    return [part.strip(" :") for part in parts if part.strip(" :")]


def _merge_payload(current_payload: SettingsPayload, updates: dict[str, object]) -> SettingsPayload:
    return SettingsPayload.model_validate(
        {
            **current_payload.model_dump(),
            **updates,
        }
    )


def _sanitize_updates(updates: dict[str, object]) -> dict[str, object]:
    allowed_lists = {
        "site_keys",
        "crawl_terms",
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
        "strict_match_groups",
    }
    allowed_scalars = {"crawl_strategy"}
    sanitized: dict[str, object] = {}
    for key, value in updates.items():
        if key in allowed_lists and isinstance(value, list):
            sanitized[key] = _dedupe([str(item).strip() for item in value if str(item).strip()])
        elif key in allowed_scalars and isinstance(value, str) and value.strip():
            sanitized[key] = value.strip()
    return sanitized


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern.casefold() in text for pattern in patterns)


def _dedupe(values: list[str]) -> list[str]:
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
