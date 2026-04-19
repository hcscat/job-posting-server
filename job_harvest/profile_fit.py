from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from job_harvest.candidate_profile import CandidateProfile, get_default_candidate_profile


RECOMMENDED_FIT_THRESHOLD = 50


@dataclass(frozen=True)
class ProfileFitAssessment:
    score: int
    level: str
    reasons: list[str]
    highlights: list[str]
    cautions: list[str]


def assess_profile_fit(
    item: Any,
    profile: CandidateProfile | None = None,
) -> ProfileFitAssessment:
    candidate = profile or get_default_candidate_profile()

    title_text = _join_text(
        _get_text(item, "title"),
        _get_text(item, "search_title"),
        _get_text(item, "page_title"),
    )
    summary_text = _join_text(
        _get_text(item, "summary"),
        _get_text(item, "description"),
        _get_text(item, "ai_summary"),
        _get_text(item, "ai_relevance_reason"),
    )
    meta_text = _join_text(
        _get_text(item, "company"),
        _get_text(item, "location"),
        _get_text(item, "employment_type"),
        _get_text(item, "experience_level"),
        _get_text(item, "education_level"),
        _get_text(item, "date_posted"),
        _get_text(item, "valid_through"),
        _get_text(item, "ai_job_family"),
        _get_text(item, "ai_seniority"),
        _get_text(item, "ai_work_model"),
    )
    stack_text = _join_text(
        *_get_list(item, "tags"),
        *_get_list(item, "ai_tech_stack"),
        *_get_list(item, "ai_requirements"),
        *_get_list(item, "ai_responsibilities"),
        *_get_list(item, "ai_benefits"),
    )
    overall_text = _join_text(title_text, summary_text, meta_text, stack_text)

    role_matches = _collect_matches(title_text + "\n" + summary_text, candidate.target_roles)
    strong_skill_matches = _collect_matches(overall_text, candidate.strong_skills)
    support_skill_matches = _collect_matches(overall_text, candidate.support_skills)
    domain_matches = _collect_matches(overall_text, candidate.target_domains)
    avoid_matches = _collect_matches(overall_text, candidate.avoid_keywords)

    score = 0
    reasons: list[str] = []
    highlights: list[str] = []
    cautions: list[str] = []

    job_family = _get_text(item, "ai_job_family").casefold()
    if job_family in candidate.preferred_job_families:
        score += 12
        reasons.append("선호 직군 분류와 일치합니다.")
    elif job_family in candidate.avoid_job_families:
        score -= 18
        cautions.append("직군 분류가 선호 영역과 거리가 있습니다.")

    if role_matches:
        role_bonus = min(28, 10 + len(role_matches) * 4)
        score += role_bonus
        reasons.append(f"직무 키워드 일치: {', '.join(role_matches[:3])}")
        highlights.extend(role_matches[:3])
    else:
        cautions.append("직무 키워드 일치가 약합니다.")

    if strong_skill_matches:
        skill_bonus = min(36, len(strong_skill_matches) * 7)
        score += skill_bonus
        reasons.append(f"주력 스택 일치: {', '.join(strong_skill_matches[:4])}")
        highlights.extend(strong_skill_matches[:4])
    else:
        score -= 8
        cautions.append("주력 스택 일치가 약합니다.")

    if support_skill_matches:
        score += min(12, len(support_skill_matches) * 3)
        if not strong_skill_matches:
            reasons.append(f"보조 스택 단서는 있습니다: {', '.join(support_skill_matches[:3])}")
        highlights.extend(support_skill_matches[:2])

    if domain_matches:
        score += min(18, len(domain_matches) * 5)
        reasons.append(f"도메인/업무 맥락 일치: {', '.join(domain_matches[:3])}")
        highlights.extend(domain_matches[:3])

    if _contains_any(overall_text, ("운영개발", "유지보수", "운영", "SM")):
        score += 8
        reasons.append("운영개발/유지보수 성격과 맞습니다.")

    if _contains_any(overall_text, ("백오피스", "관리자", "업무 시스템", "ERP", "HR")):
        score += 7
        reasons.append("업무 시스템/관리자 화면 성격과 맞습니다.")

    if _contains_any(overall_text, ("SAP UI5", "Fiori", "Nexacro", "exBuilder", "JSP")):
        score += 8
        reasons.append("경력 기반 UI 툴 경험을 바로 활용할 수 있습니다.")

    if avoid_matches:
        penalty = min(30, len(avoid_matches) * 10)
        score -= penalty
        cautions.append(f"비선호 키워드 포함: {', '.join(avoid_matches[:3])}")

    if _contains_any(title_text, ("qa", "tester", "test engineer")) and not strong_skill_matches:
        score -= 12
        cautions.append("QA 중심 공고일 가능성이 높습니다.")

    if _contains_any(overall_text, ("react", "typescript")) and not _contains_any(overall_text, ("java", "spring", "업무 시스템")):
        score -= 10
        cautions.append("현 프로필보다 프론트엔드 전용 성격이 강합니다.")

    if _contains_any(overall_text, ("node.js", "node ")) and not _contains_any(overall_text, ("java", "spring")):
        score -= 12
        cautions.append("Node.js 중심 공고로 보입니다.")

    score = max(0, min(100, score))
    level = _score_to_level(score)

    deduped_highlights = _dedupe(highlights)[:5]
    deduped_reasons = _dedupe(reasons)[:5]
    deduped_cautions = _dedupe(cautions)[:4]
    if not deduped_reasons:
        deduped_reasons = ["프로필 강점과 직접 맞닿는 신호가 많지 않습니다."]

    return ProfileFitAssessment(
        score=score,
        level=level,
        reasons=deduped_reasons,
        highlights=deduped_highlights,
        cautions=deduped_cautions,
    )


def attach_profile_fit(item: Any, profile: CandidateProfile | None = None) -> ProfileFitAssessment:
    assessment = assess_profile_fit(item, profile)
    setattr(item, "profile_fit_score", assessment.score)
    setattr(item, "profile_fit_level", assessment.level)
    setattr(item, "profile_fit_reasons", list(assessment.reasons))
    setattr(item, "profile_fit_highlights", list(assessment.highlights))
    setattr(item, "profile_fit_cautions", list(assessment.cautions))
    return assessment


def is_recommended_fit(score: int) -> bool:
    return score >= RECOMMENDED_FIT_THRESHOLD


def sort_profile_fit_key(item: Any) -> tuple[int, datetime]:
    score = int(getattr(item, "profile_fit_score", 0) or 0)
    last_seen = getattr(item, "last_seen_at", None) or datetime.min
    return score, last_seen


def _score_to_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= RECOMMENDED_FIT_THRESHOLD:
        return "medium"
    if score >= 30:
        return "low"
    return "none"


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(value.casefold() in lowered for value in values)


def _collect_matches(text: str, values: tuple[str, ...]) -> list[str]:
    lowered = text.casefold()
    matches = [value for value in values if value.casefold() in lowered]
    return _dedupe(matches)


def _join_text(*values: object) -> str:
    return " ".join(part for part in (_stringify(value) for value in values) if part)


def _get_text(item: Any, field_name: str) -> str:
    return _stringify(getattr(item, field_name, ""))


def _get_list(item: Any, field_name: str) -> list[str]:
    value = getattr(item, field_name, [])
    if not isinstance(value, list):
        return []
    return [_stringify(entry) for entry in value if _stringify(entry)]


def _stringify(value: object) -> str:
    return " ".join(str(value or "").split())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        marker = value.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(value)
    return unique
