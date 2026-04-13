from __future__ import annotations

import html
import json
from contextlib import asynccontextmanager
from math import ceil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from job_harvest.database import create_database_manager, init_database
from job_harvest.i18n import (
    LANG_COOKIE_NAME,
    build_ui_messages,
    normalize_locale,
    resolve_locale,
    translate,
)
from job_harvest.raw_store import RawSnapshotStore
from job_harvest.schemas import (
    CollectionRunRead,
    JobDetailRead,
    JobListResponse,
    JobPostingRead,
    RawSnapshotRead,
    RequestInterpretPayload,
    RequestInterpretRead,
    RunDetailRead,
    SettingsPayload,
)
from job_harvest.services import (
    CollectionAlreadyRunningError,
    CollectorService,
    SchedulerService,
    SettingsService,
)
from job_harvest.sites import BEST_EFFORT_SITE_KEYS, DEFAULT_SITES


TEMPLATES = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))
SITE_LABELS = {
    "ko": {
        "saramin": "사람인",
        "jobkorea": "잡코리아",
        "linkedin": "링크드인",
        "wanted": "원티드",
        "jumpit": "점핏",
        "remember": "리멤버",
        "jobplanet": "잡플래닛",
        "rocketpunch": "로켓펀치",
        "blind": "블라인드",
    },
    "en": {
        "saramin": "Saramin",
        "jobkorea": "JobKorea",
        "linkedin": "LinkedIn",
        "wanted": "Wanted",
        "jumpit": "Jumpit",
        "remember": "Remember",
        "jobplanet": "JobPlanet",
        "rocketpunch": "RocketPunch",
        "blind": "Blind",
    },
}

SITE_LABELS = {
    "ko": {
        "saramin": "\uc0ac\ub78c\uc778",
        "jobkorea": "\uc7a1\ucf54\ub9ac\uc544",
        "linkedin": "\ub9c1\ud06c\ub4dc\uc778",
        "wanted": "\uc6d0\ud2f0\ub4dc",
        "jumpit": "\uc810\ud54f",
        "remember": "\ub9ac\uba64\ubc84",
        "jobplanet": "\uc7a1\ud50c\ub798\ub2db",
        "rocketpunch": "\ub85c\ucf13\ud380\uce58",
        "blind": "\ube14\ub77c\uc778\ub4dc",
    },
    "en": {
        "saramin": "Saramin",
        "jobkorea": "JobKorea",
        "linkedin": "LinkedIn",
        "wanted": "Wanted",
        "jumpit": "Jumpit",
        "remember": "Remember",
        "jobplanet": "JobPlanet",
        "rocketpunch": "RocketPunch",
        "blind": "Blind",
    },
}


def translate_site_label(locale: str, site_key: str, fallback: str = "") -> str:
    return SITE_LABELS.get(locale, SITE_LABELS["en"]).get(site_key, fallback or site_key)


def _text_quality_score(value: str) -> int:
    control_penalty = sum(1 for ch in value if "\u0080" <= ch <= "\u009f") * 4
    replacement_penalty = value.count("\ufffd") * 4
    mojibake_penalty = sum(value.count(marker) for marker in ("Â", "Ã", "â", "ï»¿")) * 2
    hangul_bonus = sum(1 for ch in value if "\uac00" <= ch <= "\ud7a3") * 3
    readable_bonus = sum(1 for ch in value if ch.isalnum())
    return hangul_bonus + readable_bonus - control_penalty - replacement_penalty - mojibake_penalty


def _repair_text(value: str) -> str:
    current = html.unescape(str(value or "")).replace("\u00a0", " ")
    for _ in range(2):
        try:
            candidate = current.encode("latin1").decode("utf-8")
        except UnicodeError:
            break
        if candidate == current or _text_quality_score(candidate) <= _text_quality_score(current):
            break
        current = candidate
    return current.strip()


def _repair_value(value: Any) -> Any:
    if isinstance(value, str):
        return _repair_text(value)
    if isinstance(value, list):
        return [_repair_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _repair_value(item) for key, item in value.items()}
    return value


def _build_description_text(payload: dict[str, Any]) -> str:
    description = _repair_text(payload.get("description", ""))
    if description:
        return description

    sections: list[str] = []

    def append_section(title: str, values: list[str]) -> None:
        cleaned = []
        for value in values:
            item = _repair_text(value)
            if item:
                cleaned.append(item)
        if cleaned:
            sections.append(f"{title}\n" + "\n".join(f"- {value}" for value in cleaned))

    ai_summary = _repair_text(payload.get("ai_summary", ""))
    summary = _repair_text(payload.get("summary", ""))
    if ai_summary:
        sections.append(ai_summary)
    elif summary:
        sections.append(summary)

    append_section("Responsibilities", payload.get("ai_responsibilities", []))
    append_section("Requirements", payload.get("ai_requirements", []))
    append_section("Benefits", payload.get("ai_benefits", []))

    if not sections:
        fallback = []
        for field in ("title", "company", "location", "employment_type", "experience_level", "education_level"):
            value = _repair_text(payload.get(field, ""))
            if value:
                fallback.append(value)
        if fallback:
            sections.append(" | ".join(fallback))

    limited_capture = payload.get("status_code", 0) >= 400 or payload.get("extraction_method") == "search-result"
    if limited_capture:
        sections.append("Detail page capture was limited, so the listing-based summary is shown.")

    return "\n\n".join(section for section in sections if section).strip()


def _serialize_job_posting(item: Any) -> JobPostingRead:
    payload = JobPostingRead.model_validate(item).model_dump()
    payload = _repair_value(payload)
    payload["description"] = _build_description_text(payload)
    return JobPostingRead.model_validate(payload)


def _serialize_job_detail(item: Any) -> JobDetailRead:
    payload = JobDetailRead.model_validate(item).model_dump()
    payload = _repair_value(payload)
    payload["description"] = _build_description_text(payload)
    return JobDetailRead.model_validate(payload)


def _template_response(
    request: Request,
    *,
    name: str,
    title_key: str | None = None,
    title_text: str | None = None,
    **context,
) -> HTMLResponse:
    locale = resolve_locale(request)

    def tr(key: str, **kwargs) -> str:
        return translate(locale, key, **kwargs)

    def site_label(site_key: str, fallback: str = "") -> str:
        return translate_site_label(locale, site_key, fallback)

    response = TEMPLATES.TemplateResponse(
        request=request,
        name=name,
        context={
            "title": title_text or (tr(title_key) if title_key else ""),
            "locale": locale,
            "tr": tr,
            "site_label": site_label,
            "ui_messages_json": json.dumps(build_ui_messages(locale), ensure_ascii=False),
            "site_labels_json": json.dumps(SITE_LABELS.get(locale, SITE_LABELS["en"]), ensure_ascii=False),
            **context,
        },
    )

    requested_locale = request.query_params.get("lang")
    if requested_locale:
        response.set_cookie(
            LANG_COOKIE_NAME,
            normalize_locale(requested_locale),
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
        )
    return response


def create_app(
    database_url: str | None = None,
    data_dir: str | Path | None = None,
) -> FastAPI:
    db = create_database_manager(database_url=database_url, data_dir=data_dir)
    init_database(db)
    raw_store = RawSnapshotStore(db.data_dir)

    settings_service = SettingsService(db)
    collector_service = CollectorService(db, settings_service)
    scheduler_service = SchedulerService(settings_service, collector_service)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings_service.ensure_settings()
        yield
        db.engine.dispose()

    app = FastAPI(
        title="Job Posting Server",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=str(Path(__file__).with_name("static"))), name="static")
    app.state.settings_service = settings_service
    app.state.collector_service = collector_service
    app.state.scheduler_service = scheduler_service
    app.state.raw_store = raw_store

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        scheduler_status = scheduler_service.get_status()
        summary = collector_service.dashboard_summary(scheduler_status)
        return _template_response(
            request,
            name="dashboard.html",
            title_key="dashboard.page_title",
            summary=summary,
            settings=settings_service.get_payload(),
        )

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request) -> HTMLResponse:
        settings_payload = settings_service.get_payload()
        locale = resolve_locale(request)
        available_sites = [
            {
                "key": site.key,
                "name": translate_site_label(locale, site.key, site.name),
                "experimental": site.key in BEST_EFFORT_SITE_KEYS,
            }
            for site in DEFAULT_SITES.values()
        ]
        return _template_response(
            request,
            name="settings.html",
            title_key="settings.page_title",
            settings_json=json.dumps(settings_payload.model_dump(), ensure_ascii=False),
            available_sites=available_sites,
            strict_groups=[
                "roles",
                "keywords",
                "locations",
                "companies",
                "experience_levels",
                "education_levels",
                "employment_types",
            ],
        )

    @app.get("/jobs", response_class=HTMLResponse)
    async def jobs_page(
        request: Request,
        q: str = "",
        site: str = "",
        company: str = "",
        location: str = "",
        it_only: bool = True,
        job_family: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> HTMLResponse:
        locale = resolve_locale(request)
        result = collector_service.list_jobs(
            q=q,
            site=site,
            company=company,
            location=location,
            it_only=it_only,
            job_family=job_family,
            page=page,
            page_size=page_size,
        )
        total_pages = max(1, ceil(result.total / result.page_size)) if result.total else 1
        return _template_response(
            request,
            name="jobs.html",
            title_key="jobs.page_title",
            jobs=result.items,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            total_pages=total_pages,
            filters={
                "q": q,
                "site": site,
                "company": company,
                "location": location,
                "it_only": it_only,
                "job_family": job_family,
            },
            available_sites=[
                {
                    "key": site_item.key,
                    "name": translate_site_label(locale, site_item.key, site_item.name),
                }
                for site_item in DEFAULT_SITES.values()
            ],
            job_families=[
                "frontend",
                "backend",
                "fullstack",
                "data",
                "mobile",
                "devops",
                "security",
                "ai-ml",
                "general-software",
            ],
        )

    @app.get("/api/settings", response_model=SettingsPayload)
    async def get_settings() -> SettingsPayload:
        return settings_service.get_payload()

    @app.put("/api/settings", response_model=SettingsPayload)
    async def update_settings(payload: SettingsPayload) -> SettingsPayload:
        updated = settings_service.update_settings(payload)
        return updated

    @app.post("/api/settings/interpret", response_model=RequestInterpretRead)
    async def interpret_settings_request(payload: RequestInterpretPayload) -> RequestInterpretRead:
        return settings_service.interpret_request(
            text=payload.text,
            base_payload=payload.base_payload,
        )

    @app.post("/api/collect", response_model=CollectionRunRead)
    async def trigger_collection() -> CollectionRunRead:
        try:
            run = collector_service.run_collection(triggered_by="manual")
        except CollectionAlreadyRunningError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return CollectionRunRead.model_validate(run)

    @app.get("/api/jobs", response_model=JobListResponse)
    async def api_jobs(
        q: str = "",
        site: str = "",
        company: str = "",
        location: str = "",
        it_only: bool = True,
        job_family: str = "",
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=200),
    ) -> JobListResponse:
        result = collector_service.list_jobs(
            q=q,
            site=site,
            company=company,
            location=location,
            it_only=it_only,
            job_family=job_family,
            page=page,
            page_size=page_size,
        )
        return JobListResponse(
            items=[_serialize_job_posting(item) for item in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        )

    @app.get("/api/runs", response_model=list[CollectionRunRead])
    async def api_runs(limit: int = Query(default=50, ge=1, le=200)) -> list[CollectionRunRead]:
        return [CollectionRunRead.model_validate(run) for run in collector_service.list_runs(limit=limit)]

    @app.get("/api/runs/{run_id}", response_model=RunDetailRead)
    async def api_run_detail(run_id: int) -> RunDetailRead:
        run = collector_service.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        return RunDetailRead(
            run=CollectionRunRead.model_validate(run),
            postings=collector_service.get_run_postings(run_id),
            raw_manifest=collector_service.get_run_raw_manifest(run_id),
        )

    @app.get("/api/jobs/{job_id}", response_model=JobDetailRead)
    async def api_job_detail(job_id: int) -> JobDetailRead:
        job = collector_service.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return _serialize_job_detail(job)

    @app.get("/api/raw/{category}/{sha256_hex}", response_model=RawSnapshotRead)
    async def api_raw_snapshot(category: str, sha256_hex: str) -> RawSnapshotRead:
        if category not in {"listing", "detail"}:
            raise HTTPException(status_code=400, detail="Unsupported raw snapshot category.")
        try:
            text = raw_store.read_text(category=category, sha256_hex=sha256_hex)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Raw snapshot not found.") from exc
        return RawSnapshotRead(category=category, sha256_hex=sha256_hex, text=text)

    @app.get("/api/scheduler")
    async def api_scheduler():
        return scheduler_service.get_status()

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    async def run_detail_page(request: Request, run_id: int) -> HTMLResponse:
        run = collector_service.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        return _template_response(
            request,
            name="run_detail.html",
            title_text=translate(resolve_locale(request), "run_detail.hero_title", run_id=run_id),
            run=run,
            postings=collector_service.get_run_postings(run_id),
            raw_manifest=collector_service.get_run_raw_manifest(run_id),
        )

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    async def job_detail_page(request: Request, job_id: int) -> HTMLResponse:
        job = collector_service.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return _template_response(
            request,
            name="job_detail.html",
            title_text=job.title or job.search_title or f"Job {job_id}",
            job=job,
            raw_payload_json=json.dumps(job.raw_payload or {}, ensure_ascii=False, indent=2),
        )

    @app.get("/raw/{category}/{sha256_hex}", response_class=HTMLResponse)
    async def raw_snapshot_page(request: Request, category: str, sha256_hex: str) -> HTMLResponse:
        if category not in {"listing", "detail"}:
            raise HTTPException(status_code=400, detail="Unsupported raw snapshot category.")
        try:
            text = raw_store.read_text(category=category, sha256_hex=sha256_hex)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Raw snapshot not found.") from exc
        return _template_response(
            request,
            name="raw_snapshot.html",
            title_text=f"{category}:{sha256_hex[:12]}",
            category=category,
            sha256_hex=sha256_hex,
            text=text,
        )

    @app.get("/health")
    async def healthcheck():
        return {"status": "ok"}

    return app
