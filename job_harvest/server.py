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
from job_harvest.schemas import CollectionRunRead, JobListResponse, JobPostingRead, SettingsPayload
from job_harvest.services import (
    CollectionAlreadyRunningError,
    CollectorService,
    SchedulerService,
    SettingsService,
)
from job_harvest.sites import DEFAULT_SITES


TEMPLATES = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def create_app(
    database_url: str | None = None,
    data_dir: str | Path | None = None,
) -> FastAPI:
    db = create_database_manager(database_url=database_url, data_dir=data_dir)
    init_database(db)

    settings_service = SettingsService(db)
    collector_service = CollectorService(db, settings_service)
    scheduler_service = SchedulerService(settings_service, collector_service)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings_service.ensure_settings()
        scheduler_service.start()
        yield
        scheduler_service.shutdown()
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

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        scheduler_status = scheduler_service.get_status()
        summary = collector_service.dashboard_summary(scheduler_status)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "title": "Dashboard",
                "summary": summary,
                "settings": settings_service.get_payload(),
            },
        )

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request) -> HTMLResponse:
        settings_payload = settings_service.get_payload()
        available_sites = [
            {
                "key": site.key,
                "name": site.name,
                "experimental": site.key not in {"saramin", "jobkorea", "linkedin"},
            }
            for site in DEFAULT_SITES.values()
        ]
        return TEMPLATES.TemplateResponse(
            request=request,
            name="settings.html",
            context={
                "title": "Settings",
                "settings_json": json.dumps(settings_payload.model_dump(), ensure_ascii=False),
                "available_sites": available_sites,
                "strict_groups": [
                    "roles",
                    "keywords",
                    "locations",
                    "companies",
                    "experience_levels",
                    "education_levels",
                    "employment_types",
                ],
            },
        )

    @app.get("/jobs", response_class=HTMLResponse)
    async def jobs_page(
        request: Request,
        q: str = "",
        site: str = "",
        company: str = "",
        location: str = "",
        page: int = 1,
        page_size: int = 25,
    ) -> HTMLResponse:
        result = collector_service.list_jobs(
            q=q,
            site=site,
            company=company,
            location=location,
            page=page,
            page_size=page_size,
        )
        total_pages = max(1, ceil(result.total / result.page_size)) if result.total else 1
        return TEMPLATES.TemplateResponse(
            request=request,
            name="jobs.html",
            context={
                "title": "Jobs",
                "jobs": result.items,
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "total_pages": total_pages,
                "filters": {"q": q, "site": site, "company": company, "location": location},
                "available_sites": list(DEFAULT_SITES.values()),
            },
        )

    @app.get("/api/settings", response_model=SettingsPayload)
    async def get_settings() -> SettingsPayload:
        return settings_service.get_payload()

    @app.put("/api/settings", response_model=SettingsPayload)
    async def update_settings(payload: SettingsPayload) -> SettingsPayload:
        updated = settings_service.update_settings(payload)
        scheduler_service.rebuild_schedule()
        return updated

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
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=200),
    ) -> JobListResponse:
        result = collector_service.list_jobs(
            q=q,
            site=site,
            company=company,
            location=location,
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
    async def api_runs(limit: int = Query(default=20, ge=1, le=100)) -> list[CollectionRunRead]:
        return [CollectionRunRead.model_validate(run) for run in collector_service.list_runs(limit=limit)]

    @app.get("/api/scheduler")
    async def api_scheduler():
        return scheduler_service.get_status()

    @app.get("/health")
    async def healthcheck():
        return {"status": "ok"}

    return app
