from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


PROFILE_SOURCE_FILENAME = "portfolio_profile_base_20260419.md"


@dataclass(frozen=True)
class CandidateProfile:
    key: str
    title: str
    headline: str
    summary: str
    target_roles: tuple[str, ...]
    strong_skills: tuple[str, ...]
    support_skills: tuple[str, ...]
    target_domains: tuple[str, ...]
    preferred_job_families: tuple[str, ...]
    avoid_job_families: tuple[str, ...]
    avoid_keywords: tuple[str, ...]
    preferred_locations: tuple[str, ...]
    collection_queries: tuple[str, ...]
    collection_exclude_keywords: tuple[str, ...]

    @property
    def source_document(self) -> str:
        return PROFILE_SOURCE_FILENAME


DEFAULT_CANDIDATE_PROFILE = CandidateProfile(
    key="enterprise-java-profile",
    title="엔터프라이즈 업무 시스템 웹개발자",
    headline="Java/Spring 기반 공공·이커머스 운영개발 포지션 중심 프로필",
    summary=(
        "QA/QC 기반 품질 관점과 Java/Spring 업무 시스템 개발 경험을 함께 가진 개발자 프로필이다. "
        "공공 시스템, 이커머스 운영개발, 백오피스/관리자 화면, SI/SM, SAP UI5/Fiori, "
        "Nexacro, exBuilder 계열 포지션을 우선 수집 대상으로 본다."
    ),
    target_roles=(
        "웹 개발자",
        "백엔드 개발자",
        "풀스택 개발자",
        "업무 시스템 개발자",
        "운영개발",
        "SI 개발",
        "SM 개발",
        "백오피스 개발자",
        "관리자 화면 개발",
        "SAP UI5 개발자",
        "Nexacro 개발자",
        "exBuilder 개발자",
        "Java 개발자",
        "Spring 개발자",
    ),
    strong_skills=(
        "Java",
        "Spring",
        "MyBatis",
        "JavaScript",
        "JSP",
        "Oracle",
        "MSSQL",
        "MS-SQL",
        "Nexacro",
        "exBuilder",
        "exBuilder6",
        "SAP UI5",
        "Fiori",
    ),
    support_skills=(
        "PostgreSQL",
        "SQL",
        "Linux",
        "CentOS",
        "Shell Script",
        "Selenium",
        "Jenkins",
        "Git",
        "GitLab",
        "SVN",
        "pdf.js",
        "Blob",
        "CSS",
    ),
    target_domains=(
        "공공",
        "이커머스",
        "업무 시스템",
        "운영개발",
        "백오피스",
        "관리자",
        "SI",
        "SM",
        "ERP",
        "HR",
        "그룹웨어",
    ),
    preferred_job_families=("backend", "fullstack", "frontend", "general-software"),
    avoid_job_families=("data", "mobile", "devops", "security", "ai-ml"),
    avoid_keywords=(
        "디자이너",
        "퍼블리셔",
        "마케팅",
        "영업",
        "간호",
        "교수",
        "데이터 사이언티스트",
        "머신러닝",
        "AI Research",
        "Node.js",
        "DevOps",
        "SRE",
        "Android",
        "iOS",
    ),
    preferred_locations=("서울", "경기", "판교", "분당"),
    collection_queries=(
        "Java Spring 업무 시스템 개발자",
        "Java Spring 운영개발",
        "Java MyBatis 공공 시스템 개발",
        "Java JSP Nexacro 개발자",
        "exBuilder Java Oracle 개발",
        "SAP UI5 Fiori JavaScript 개발",
        "이커머스 운영개발 Java",
        "백오피스 Java 개발",
    ),
    collection_exclude_keywords=(
        "디자이너",
        "퍼블리셔",
        "마케팅",
        "영업",
        "간호",
        "교수",
    ),
)


def get_default_candidate_profile() -> CandidateProfile:
    return DEFAULT_CANDIDATE_PROFILE


def get_profile_source_path() -> Path:
    return Path(__file__).resolve().parents[1] / PROFILE_SOURCE_FILENAME


def build_profile_context() -> dict[str, object]:
    profile = get_default_candidate_profile()
    payload = asdict(profile)
    payload["source_document"] = profile.source_document
    payload["source_document_exists"] = get_profile_source_path().exists()
    return payload


def build_profile_collection_settings(*, output_dir: str) -> dict[str, object]:
    profile = get_default_candidate_profile()
    return {
        "site_keys": [
            "saramin",
            "jobkorea",
            "linkedin",
            "wanted",
            "jumpit",
            "remember",
            "jobplanet",
            "rocketpunch",
            "blind",
        ],
        "queries": list(profile.collection_queries),
        "crawl_strategy": "query_search",
        "crawl_terms": list(profile.strong_skills[:8]),
        "listing_page_limit": 4,
        "roles": list(profile.target_roles),
        "keywords": list(profile.strong_skills + profile.target_domains),
        "exclude_keywords": list(profile.collection_exclude_keywords),
        "locations": [],
        "companies": [],
        "experience_levels": [],
        "education_levels": [],
        "employment_types": [],
        "required_terms": [],
        "industries": [],
        "salary_ranges": [],
        "company_types": [],
        "company_sizes": [],
        "position_levels": [],
        "majors": [],
        "certifications": [],
        "preferred_conditions": [],
        "welfare": [],
        "skills": [],
        "tags": [],
        "workplace_types": [],
        "date_posted": [],
        "deadline": [],
        "easy_apply": [],
        "applicant_signals": [],
        "network_signals": [],
        "leader_positions": [],
        "headhunting": [],
        "theme_tags": [],
        "extra_terms": ["채용", "공고", "운영개발", "업무 시스템"],
        "strict_match_groups": ["roles"],
        "max_results_per_site": 40,
        "request_timeout_seconds": 20,
        "fetch_details": True,
        "store_html": False,
        "detail_refetch_hours": 24,
        "concurrency": 4,
        "pause_between_searches_seconds": 1.5,
        "ai_enrichment_enabled": False,
        "ai_provider": "heuristic",
        "ai_model": "",
        "browser_enabled": True,
        "browser_headless": True,
        "browser_timeout_seconds": 60,
        "output_dir": output_dir,
        "schedule_enabled": False,
        "schedule_mode": "fixed_times",
        "schedule_times": ["09:00"],
        "schedule_interval_hours": 24,
        "schedule_run_on_start": False,
        "schedule_timezone": "Asia/Seoul",
    }
