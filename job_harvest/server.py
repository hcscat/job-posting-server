from __future__ import annotations

import json
from contextlib import asynccontextmanager
from math import ceil
from pathlib import Path

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

    response = TEMPLATES.TemplateResponse(
        request=request,
        name=name,
        context={
            "title": title_text or (tr(title_key) if title_key else ""),
            "locale": locale,
            "tr": tr,
            "ui_messages_json": json.dumps(build_ui_messages(locale), ensure_ascii=False),
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
        available_sites = [
            {
                "key": site.key,
                "name": site.name,
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
            available_sites=list(DEFAULT_SITES.values()),
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
            items=[JobPostingRead.model_validate(item) for item in result.items],
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
        return JobDetailRead.model_validate(job)

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
