from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Iterable

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, or_, select

from job_harvest.config import AppConfig, build_config, config_to_dict, load_config
from job_harvest.database import DatabaseManager
from job_harvest.db_models import AppSettingsRecord, CollectionRunRecord, JobPostingRecord, utcnow
from job_harvest.models import JobPosting
from job_harvest.runner import collect_postings
from job_harvest.schemas import (
    DashboardSummaryRead,
    SchedulerJobRead,
    SchedulerStatusRead,
    SettingsPayload,
    SiteCountRead,
)
from job_harvest.storage import persist_run


class CollectionAlreadyRunningError(RuntimeError):
    pass


@dataclass
class JobListPage:
    items: list[JobPostingRecord]
    total: int
    page: int
    page_size: int


class SettingsService:
    def __init__(self, db: DatabaseManager, bootstrap_config_path: str | Path = "config.yaml") -> None:
        self._db = db
        self._bootstrap_config_path = Path(bootstrap_config_path)

    def ensure_settings(self) -> SettingsPayload:
        with self._db.session_factory() as session:
            record = session.get(AppSettingsRecord, 1)
            if record is None:
                payload = self._bootstrap_payload()
                record = AppSettingsRecord(id=1)
                self._apply_payload(record, payload)
                session.add(record)
                session.commit()
                session.refresh(record)
            return self._to_payload(record)

    def get_payload(self) -> SettingsPayload:
        with self._db.session_factory() as session:
            record = session.get(AppSettingsRecord, 1)
            if record is None:
                return self.ensure_settings()
            return self._to_payload(record)

    def update_settings(self, payload: SettingsPayload) -> SettingsPayload:
        with self._db.session_factory() as session:
            record = session.get(AppSettingsRecord, 1)
            if record is None:
                record = AppSettingsRecord(id=1)
                session.add(record)
            self._apply_payload(record, payload)
            session.commit()
            session.refresh(record)
            return self._to_payload(record)

    def get_app_config(self) -> AppConfig:
        payload = self.get_payload()
        config_dict = {
            "output_dir": payload.output_dir,
            "search": {
                "sites": payload.site_keys,
                "queries": payload.queries,
                "max_results_per_site": payload.max_results_per_site,
                "request_timeout_seconds": payload.request_timeout_seconds,
                "fetch_details": payload.fetch_details,
                "store_html": payload.store_html,
                "concurrency": payload.concurrency,
                "pause_between_searches_seconds": payload.pause_between_searches_seconds,
                "user_agent": payload.user_agent,
            },
            "criteria": {
                "roles": payload.roles,
                "keywords": payload.keywords,
                "exclude_keywords": payload.exclude_keywords,
                "locations": payload.locations,
                "companies": payload.companies,
                "experience_levels": payload.experience_levels,
                "education_levels": payload.education_levels,
                "employment_types": payload.employment_types,
                "required_terms": payload.required_terms,
                "extra_terms": payload.extra_terms,
                "strict_match_groups": payload.strict_match_groups,
            },
            "schedule": {
                "enabled": payload.schedule_enabled,
                "timezone": payload.schedule_timezone,
                "mode": payload.schedule_mode,
                "times": payload.schedule_times,
                "interval_hours": payload.schedule_interval_hours,
                "run_on_start": payload.schedule_run_on_start,
                "max_runs": None,
            },
        }
        return build_config(config_dict, base_dir=".", source="database")

    def _bootstrap_payload(self) -> SettingsPayload:
        if self._bootstrap_config_path.exists():
            config = load_config(self._bootstrap_config_path)
            payload = config_to_dict(config)
            return SettingsPayload(
                site_keys=payload["search"]["sites"],
                queries=payload["search"]["queries"],
                roles=payload["criteria"]["roles"],
                keywords=payload["criteria"]["keywords"],
                exclude_keywords=payload["criteria"]["exclude_keywords"],
                locations=payload["criteria"]["locations"],
                companies=payload["criteria"]["companies"],
                experience_levels=payload["criteria"]["experience_levels"],
                education_levels=payload["criteria"]["education_levels"],
                employment_types=payload["criteria"]["employment_types"],
                required_terms=payload["criteria"]["required_terms"],
                extra_terms=payload["criteria"]["extra_terms"],
                strict_match_groups=payload["criteria"]["strict_match_groups"],
                max_results_per_site=payload["search"]["max_results_per_site"],
                request_timeout_seconds=payload["search"]["request_timeout_seconds"],
                fetch_details=payload["search"]["fetch_details"],
                store_html=payload["search"]["store_html"],
                concurrency=payload["search"]["concurrency"],
                pause_between_searches_seconds=payload["search"]["pause_between_searches_seconds"],
                user_agent=payload["search"]["user_agent"],
                output_dir=payload["output_dir"],
                schedule_enabled=payload["schedule"]["enabled"],
                schedule_mode=payload["schedule"]["mode"],
                schedule_times=payload["schedule"]["times"],
                schedule_interval_hours=payload["schedule"]["interval_hours"],
                schedule_run_on_start=payload["schedule"]["run_on_start"],
                schedule_timezone=payload["schedule"]["timezone"],
            )
        return SettingsPayload(output_dir=str(self._db.export_dir))

    def _to_payload(self, record: AppSettingsRecord) -> SettingsPayload:
        return SettingsPayload(
            site_keys=list(record.site_keys),
            queries=list(record.queries),
            roles=list(record.roles),
            keywords=list(record.keywords),
            exclude_keywords=list(record.exclude_keywords),
            locations=list(record.locations),
            companies=list(record.companies),
            experience_levels=list(record.experience_levels),
            education_levels=list(record.education_levels),
            employment_types=list(record.employment_types),
            required_terms=list(record.required_terms),
            extra_terms=list(record.extra_terms),
            strict_match_groups=list(record.strict_match_groups),
            max_results_per_site=record.max_results_per_site,
            request_timeout_seconds=record.request_timeout_seconds,
            fetch_details=record.fetch_details,
            store_html=record.store_html,
            concurrency=record.concurrency,
            pause_between_searches_seconds=record.pause_between_searches_seconds,
            user_agent=record.user_agent,
            output_dir=record.output_dir,
            schedule_enabled=record.schedule_enabled,
            schedule_mode=record.schedule_mode,
            schedule_times=list(record.schedule_times),
            schedule_interval_hours=record.schedule_interval_hours,
            schedule_run_on_start=record.schedule_run_on_start,
            schedule_timezone=record.schedule_timezone,
        )

    def _apply_payload(self, record: AppSettingsRecord, payload: SettingsPayload) -> None:
        record.site_keys = list(payload.site_keys)
        record.queries = list(payload.queries)
        record.roles = list(payload.roles)
        record.keywords = list(payload.keywords)
        record.exclude_keywords = list(payload.exclude_keywords)
        record.locations = list(payload.locations)
        record.companies = list(payload.companies)
        record.experience_levels = list(payload.experience_levels)
        record.education_levels = list(payload.education_levels)
        record.employment_types = list(payload.employment_types)
        record.required_terms = list(payload.required_terms)
        record.extra_terms = list(payload.extra_terms)
        record.strict_match_groups = list(payload.strict_match_groups)
        record.max_results_per_site = payload.max_results_per_site
        record.request_timeout_seconds = payload.request_timeout_seconds
        record.fetch_details = payload.fetch_details
        record.store_html = payload.store_html
        record.concurrency = payload.concurrency
        record.pause_between_searches_seconds = payload.pause_between_searches_seconds
        record.user_agent = payload.user_agent
        record.output_dir = payload.output_dir
        record.schedule_enabled = payload.schedule_enabled
        record.schedule_mode = payload.schedule_mode
        record.schedule_times = list(payload.schedule_times)
        record.schedule_interval_hours = payload.schedule_interval_hours
        record.schedule_run_on_start = payload.schedule_run_on_start
        record.schedule_timezone = payload.schedule_timezone


class CollectorService:
    def __init__(self, db: DatabaseManager, settings_service: SettingsService) -> None:
        self._db = db
        self._settings_service = settings_service
        self._lock = Lock()

    def is_collecting(self) -> bool:
        return self._lock.locked()

    def run_collection(self, triggered_by: str = "manual") -> CollectionRunRecord:
        if not self._lock.acquire(blocking=False):
            raise CollectionAlreadyRunningError("A collection run is already in progress.")

        run_id: int | None = None
        try:
            settings = self._settings_service.get_payload()
            with self._db.session_factory() as session:
                run = CollectionRunRecord(
                    triggered_by=triggered_by,
                    status="running",
                    site_keys=list(settings.site_keys),
                    query_terms=list(settings.queries),
                    started_at=utcnow(),
                )
                session.add(run)
                session.commit()
                session.refresh(run)
                run_id = run.id

            config = self._settings_service.get_app_config()
            execution = collect_postings(config)
            export_dir = persist_run(
                output_dir=config.output_dir,
                postings=execution.filtered_postings,
                queries=execution.queries,
                config_source=config.config_source,
                store_html=config.search.store_html,
                html_by_url=execution.html_by_url,
            )

            with self._db.session_factory() as session:
                run = session.get(CollectionRunRecord, run_id)
                if run is None:
                    raise RuntimeError("Collection run disappeared before it could be finalized.")
                new_count, updated_count = self._upsert_postings(session, execution.filtered_postings, run.id)
                run.status = "success"
                run.message = f"Saved {len(execution.filtered_postings)} postings."
                run.hit_count = len(execution.hits)
                run.unique_hit_count = len(execution.deduped_hits)
                run.saved_count = len(execution.filtered_postings)
                run.new_count = new_count
                run.updated_count = updated_count
                run.query_terms = list(execution.queries)
                run.site_keys = list(settings.site_keys)
                run.export_path = str(export_dir)
                run.finished_at = utcnow()
                session.commit()
                session.refresh(run)
                return run
        except Exception as exc:
            if run_id is not None:
                with self._db.session_factory() as session:
                    run = session.get(CollectionRunRecord, run_id)
                    if run is not None:
                        run.status = "failed"
                        run.message = str(exc)
                        run.finished_at = utcnow()
                        session.commit()
            raise
        finally:
            self._lock.release()

    def list_jobs(
        self,
        *,
        q: str = "",
        site: str = "",
        company: str = "",
        location: str = "",
        page: int = 1,
        page_size: int = 25,
    ) -> JobListPage:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 200))
        with self._db.session_factory() as session:
            stmt = select(JobPostingRecord)
            if q:
                like = f"%{q.strip()}%"
                stmt = stmt.where(
                    or_(
                        JobPostingRecord.title.ilike(like),
                        JobPostingRecord.company.ilike(like),
                        JobPostingRecord.location.ilike(like),
                        JobPostingRecord.summary.ilike(like),
                    )
                )
            if site:
                stmt = stmt.where(JobPostingRecord.site_key == site)
            if company:
                stmt = stmt.where(JobPostingRecord.company.ilike(f"%{company.strip()}%"))
            if location:
                stmt = stmt.where(JobPostingRecord.location.ilike(f"%{location.strip()}%"))

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = int(session.scalar(count_stmt) or 0)
            stmt = stmt.order_by(JobPostingRecord.last_seen_at.desc())
            stmt = stmt.offset((safe_page - 1) * safe_page_size).limit(safe_page_size)
            items = list(session.scalars(stmt).all())
            return JobListPage(items=items, total=total, page=safe_page, page_size=safe_page_size)

    def list_runs(self, limit: int = 20) -> list[CollectionRunRecord]:
        with self._db.session_factory() as session:
            stmt = select(CollectionRunRecord).order_by(CollectionRunRecord.started_at.desc()).limit(limit)
            return list(session.scalars(stmt).all())

    def dashboard_summary(self, scheduler_status: SchedulerStatusRead) -> DashboardSummaryRead:
        with self._db.session_factory() as session:
            total_postings = int(session.scalar(select(func.count(JobPostingRecord.id))) or 0)
            total_runs = int(session.scalar(select(func.count(CollectionRunRecord.id))) or 0)
            recent_runs = list(
                session.scalars(
                    select(CollectionRunRecord).order_by(CollectionRunRecord.started_at.desc()).limit(8)
                ).all()
            )
            site_rows = session.execute(
                select(JobPostingRecord.site_name, func.count(JobPostingRecord.id))
                .group_by(JobPostingRecord.site_name)
                .order_by(func.count(JobPostingRecord.id).desc())
            ).all()
        return DashboardSummaryRead(
            total_postings=total_postings,
            total_runs=total_runs,
            is_collecting=self.is_collecting(),
            site_counts=[SiteCountRead(site_name=name, count=count) for name, count in site_rows],
            recent_runs=recent_runs,
            scheduler=scheduler_status,
        )

    def _upsert_postings(
        self,
        session,
        postings: Iterable[JobPosting],
        run_id: int,
    ) -> tuple[int, int]:
        posting_list = list(postings)
        if not posting_list:
            return 0, 0

        urls = [posting.normalized_url for posting in posting_list]
        stmt = select(JobPostingRecord).where(JobPostingRecord.normalized_url.in_(urls))
        existing_records = {
            record.normalized_url: record
            for record in session.scalars(stmt).all()
        }

        new_count = 0
        updated_count = 0
        now = utcnow()
        for posting in posting_list:
            record = existing_records.get(posting.normalized_url)
            discovered_at = _parse_iso_datetime(posting.discovered_at)
            payload = posting.to_dict()
            if record is None:
                record = JobPostingRecord(
                    latest_run_id=run_id,
                    normalized_url=posting.normalized_url,
                    url=posting.url,
                    site_key=posting.site_key,
                    site_name=posting.site_name,
                    source_query=posting.source_query,
                    title=posting.title,
                    search_title=posting.search_title,
                    search_snippet=posting.search_snippet,
                    page_title=posting.page_title,
                    company=posting.company,
                    location=posting.location,
                    employment_type=posting.employment_type,
                    experience_level=posting.experience_level,
                    education_level=posting.education_level,
                    date_posted=posting.date_posted,
                    valid_through=posting.valid_through,
                    pub_date=posting.pub_date,
                    summary=posting.summary,
                    description=posting.description,
                    extraction_method=posting.extraction_method,
                    status_code=posting.status_code,
                    html_path=posting.html_path,
                    tags=list(posting.tags),
                    raw_payload=payload,
                    discovered_at=discovered_at,
                    first_seen_at=now,
                    last_seen_at=now,
                    seen_count=1,
                )
                session.add(record)
                new_count += 1
                continue

            record.latest_run_id = run_id
            record.url = posting.url
            record.site_key = posting.site_key
            record.site_name = posting.site_name
            record.source_query = posting.source_query
            record.title = posting.title
            record.search_title = posting.search_title
            record.search_snippet = posting.search_snippet
            record.page_title = posting.page_title
            record.company = posting.company
            record.location = posting.location
            record.employment_type = posting.employment_type
            record.experience_level = posting.experience_level
            record.education_level = posting.education_level
            record.date_posted = posting.date_posted
            record.valid_through = posting.valid_through
            record.pub_date = posting.pub_date
            record.summary = posting.summary
            record.description = posting.description
            record.extraction_method = posting.extraction_method
            record.status_code = posting.status_code
            record.html_path = posting.html_path
            record.tags = list(posting.tags)
            record.raw_payload = payload
            record.discovered_at = discovered_at
            record.last_seen_at = now
            record.seen_count += 1
            updated_count += 1

        session.commit()
        return new_count, updated_count


class SchedulerService:
    def __init__(self, settings_service: SettingsService, collector_service: CollectorService) -> None:
        self._settings_service = settings_service
        self._collector_service = collector_service
        self._scheduler = BackgroundScheduler(job_defaults={"coalesce": True, "max_instances": 1})
        self._started = False
        self._startup_run_triggered = False

    @property
    def running(self) -> bool:
        return self._started

    def start(self) -> None:
        if not self._started:
            self._scheduler.start()
            self._started = True
        self.rebuild_schedule()
        settings = self._settings_service.get_payload()
        if settings.schedule_enabled and settings.schedule_run_on_start and not self._startup_run_triggered:
            self._startup_run_triggered = True
            Thread(target=self._safe_collect, args=("startup",), daemon=True).start()

    def shutdown(self) -> None:
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False

    def rebuild_schedule(self) -> None:
        settings = self._settings_service.get_payload()
        self._scheduler.remove_all_jobs()
        if not settings.schedule_enabled:
            return

        if settings.schedule_mode == "fixed_times":
            for index, time_value in enumerate(settings.schedule_times):
                hour_text, minute_text = time_value.split(":", 1)
                self._scheduler.add_job(
                    self._safe_collect,
                    trigger="cron",
                    id=f"collect-fixed-{index}",
                    replace_existing=True,
                    hour=int(hour_text),
                    minute=int(minute_text),
                    timezone=settings.schedule_timezone,
                    kwargs={"triggered_by": "schedule"},
                )
            return

        self._scheduler.add_job(
            self._safe_collect,
            trigger="interval",
            id="collect-interval",
            replace_existing=True,
            hours=settings.schedule_interval_hours,
            kwargs={"triggered_by": "schedule"},
        )

    def get_status(self) -> SchedulerStatusRead:
        jobs = [
            SchedulerJobRead(
                job_id=job.id,
                description=str(job.trigger),
                next_run_at=job.next_run_time.isoformat() if job.next_run_time else None,
            )
            for job in self._scheduler.get_jobs()
        ]
        return SchedulerStatusRead(running=self.running, jobs=jobs)

    def _safe_collect(self, triggered_by: str) -> None:
        try:
            self._collector_service.run_collection(triggered_by=triggered_by)
        except CollectionAlreadyRunningError:
            print("[job_harvest] skipped scheduled run because another run is in progress.", flush=True)
        except Exception as exc:
            print(f"[job_harvest] scheduled run failed: {exc}", flush=True)


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
