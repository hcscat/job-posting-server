from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from job_harvest.config import AppConfig
from job_harvest.models import JobPosting


IT_KEYWORDS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "vue",
    "angular",
    "node",
    "node.js",
    "backend",
    "front-end",
    "frontend",
    "fullstack",
    "full-stack",
    "software",
    "engineer",
    "developer",
    "devops",
    "kubernetes",
    "docker",
    "aws",
    "gcp",
    "azure",
    "sql",
    "nosql",
    "spring",
    "django",
    "flask",
    "fastapi",
    "ml",
    "machine learning",
    "ai",
    "data engineer",
    "data scientist",
    "security engineer",
    "클라우드",
    "개발",
    "개발자",
    "프론트엔드",
    "백엔드",
    "풀스택",
    "서버",
    "데이터",
    "소프트웨어",
    "엔지니어",
    "devops",
    "보안",
}
BENEFIT_HINTS = ("복지", "benefit", "지원", "보험", "휴가", "재택", "원격", "stock", "equity")
REQUIREMENT_HINTS = ("자격", "requirement", "필수", "우대", "경험", "skill", "qualification")
RESPONSIBILITY_HINTS = ("업무", "responsibility", "담당", "주요업무", "what you will do")
WORK_MODEL_HINTS = {
    "remote": ("remote", "원격", "재택"),
    "hybrid": ("hybrid", "하이브리드"),
    "onsite": ("on-site", "onsite", "상주", "출근"),
}


@dataclass
class JobEnrichment:
    is_it_job: bool
    provider: str
    model: str
    summary: str
    relevance_reason: str
    job_family: str
    seniority: str
    work_model: str
    tech_stack: list[str]
    requirements: list[str]
    responsibilities: list[str]
    benefits: list[str]
    enriched_at: str


class BaseEnricher:
    provider = "heuristic"

    def enrich(self, posting: JobPosting) -> JobEnrichment:
        raise NotImplementedError


class HeuristicEnricher(BaseEnricher):
    provider = "heuristic"

    def __init__(self, model: str = "local-heuristic") -> None:
        self._model = model

    def enrich(self, posting: JobPosting) -> JobEnrichment:
        text = " ".join(
            [
                posting.title,
                posting.search_title,
                posting.summary,
                posting.description,
                " ".join(posting.tags),
            ]
        )
        lowered = text.casefold()
        tech_stack = sorted({keyword for keyword in IT_KEYWORDS if keyword in lowered})[:20]
        is_it_job = bool(tech_stack) or any(token in lowered for token in ("개발", "engineer", "developer"))
        summary = summarize_text(text)
        requirements = extract_bullets(posting.description, REQUIREMENT_HINTS)
        responsibilities = extract_bullets(posting.description, RESPONSIBILITY_HINTS)
        benefits = extract_bullets(posting.description, BENEFIT_HINTS)

        return JobEnrichment(
            is_it_job=is_it_job,
            provider=self.provider,
            model=self._model,
            summary=summary,
            relevance_reason=(
                "Detected common software-engineering keywords in title or detail content."
                if is_it_job
                else "No strong software-engineering keywords were detected."
            ),
            job_family=detect_job_family(lowered),
            seniority=detect_seniority(lowered),
            work_model=detect_work_model(lowered),
            tech_stack=tech_stack,
            requirements=requirements,
            responsibilities=responsibilities,
            benefits=benefits,
            enriched_at=datetime.now(timezone.utc).isoformat(),
        )


class OpenAIEnricher(BaseEnricher):
    provider = "openai"

    def __init__(self, model: str) -> None:
        self._model = model

    def enrich(self, posting: JobPosting) -> JobEnrichment:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")

        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        prompt = build_prompt(posting)
        response = client.responses.create(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You extract structured information from job postings. "
                                "Return strict JSON only with keys: "
                                "is_it_job, summary, relevance_reason, job_family, seniority, "
                                "work_model, tech_stack, requirements, responsibilities, benefits."
                            ),
                        }
                    ],
                },
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
        )
        payload = json.loads(response.output_text)
        return JobEnrichment(
            is_it_job=bool(payload.get("is_it_job")),
            provider=self.provider,
            model=self._model,
            summary=clean_text(payload.get("summary", "")),
            relevance_reason=clean_text(payload.get("relevance_reason", "")),
            job_family=clean_text(payload.get("job_family", "")),
            seniority=clean_text(payload.get("seniority", "")),
            work_model=clean_text(payload.get("work_model", "")),
            tech_stack=clean_list(payload.get("tech_stack")),
            requirements=clean_list(payload.get("requirements")),
            responsibilities=clean_list(payload.get("responsibilities")),
            benefits=clean_list(payload.get("benefits")),
            enriched_at=datetime.now(timezone.utc).isoformat(),
        )


def build_enricher(config: AppConfig) -> BaseEnricher:
    if config.search.ai_enrichment_enabled and config.search.ai_provider == "openai":
        if config.search.ai_model:
            return OpenAIEnricher(config.search.ai_model)
    return HeuristicEnricher()


def apply_enrichment(posting: JobPosting, enrichment: JobEnrichment) -> JobPosting:
    posting.is_it_job = enrichment.is_it_job
    posting.ai_provider = enrichment.provider
    posting.ai_model = enrichment.model
    posting.ai_summary = enrichment.summary
    posting.ai_relevance_reason = enrichment.relevance_reason
    posting.ai_job_family = enrichment.job_family
    posting.ai_seniority = enrichment.seniority
    posting.ai_work_model = enrichment.work_model
    posting.ai_tech_stack = list(enrichment.tech_stack)
    posting.ai_requirements = list(enrichment.requirements)
    posting.ai_responsibilities = list(enrichment.responsibilities)
    posting.ai_benefits = list(enrichment.benefits)
    posting.enriched_at = enrichment.enriched_at
    if enrichment.summary and not posting.summary:
        posting.summary = enrichment.summary
    return posting


def build_prompt(posting: JobPosting) -> str:
    return "\n\n".join(
        [
            f"Title: {posting.title or posting.search_title}",
            f"Company: {posting.company}",
            f"Location: {posting.location}",
            f"Employment type: {posting.employment_type}",
            f"Experience: {posting.experience_level}",
            f"Education: {posting.education_level}",
            f"Summary: {posting.summary}",
            f"Description: {posting.description[:12000]}",
        ]
    )


def summarize_text(text: str, max_sentences: int = 3) -> str:
    chunks = [chunk.strip() for chunk in re.split(r"(?<=[.!?。！？])\s+|\n+", text) if chunk.strip()]
    if not chunks:
        return ""
    return " ".join(chunks[:max_sentences])[:500]


def extract_bullets(text: str, hints: Iterable[str], limit: int = 6) -> list[str]:
    lines = [clean_text(line) for line in re.split(r"[\r\n]+", text or "") if clean_text(line)]
    hinted: list[str] = []
    for line in lines:
        lowered = line.casefold()
        if any(hint in lowered for hint in hints):
            hinted.append(line)
    if hinted:
        return hinted[:limit]
    return lines[:limit]


def detect_job_family(text: str) -> str:
    families = {
        "frontend": ("frontend", "front-end", "프론트엔드"),
        "backend": ("backend", "백엔드", "server"),
        "fullstack": ("fullstack", "full-stack", "풀스택"),
        "data": ("data engineer", "data scientist", "데이터"),
        "mobile": ("android", "ios", "mobile", "앱"),
        "devops": ("devops", "sre", "platform", "infra", "인프라"),
        "security": ("security", "보안"),
        "ai-ml": ("machine learning", "ml", "ai", "llm"),
    }
    for family, keywords in families.items():
        if any(keyword in text for keyword in keywords):
            return family
    return "general-software"


def detect_seniority(text: str) -> str:
    hints = {
        "intern": ("intern", "인턴"),
        "junior": ("junior", "신입", "entry"),
        "mid": ("mid", "3년", "4년", "5년"),
        "senior": ("senior", "lead", "staff", "principal", "책임", "수석"),
    }
    for level, keywords in hints.items():
        if any(keyword in text for keyword in keywords):
            return level
    return ""


def detect_work_model(text: str) -> str:
    for model, keywords in WORK_MODEL_HINTS.items():
        if any(keyword in text for keyword in keywords):
            return model
    return ""


def clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def clean_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if value is None:
        return []
    text = clean_text(value)
    if not text:
        return []
    return [part for part in re.split(r"[;,]\s*", text) if part]
