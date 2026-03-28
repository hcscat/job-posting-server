from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


@dataclass
class DatabaseManager:
    database_url: str
    engine: Engine
    session_factory: sessionmaker[Session]
    data_dir: Path
    export_dir: Path


def create_database_manager(
    database_url: str | None = None,
    data_dir: str | Path | None = None,
) -> DatabaseManager:
    resolved_data_dir = Path(
        data_dir or os.getenv("JOB_HARVEST_DATA_DIR", "./data")
    ).expanduser().resolve()
    resolved_data_dir.mkdir(parents=True, exist_ok=True)

    resolved_database_url = database_url or os.getenv("JOB_HARVEST_DATABASE_URL")
    if not resolved_database_url:
        database_path = resolved_data_dir / "app.db"
        resolved_database_url = f"sqlite:///{database_path.as_posix()}"

    export_dir = resolved_data_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    connect_args = {"check_same_thread": False} if resolved_database_url.startswith("sqlite") else {}
    engine = create_engine(resolved_database_url, connect_args=connect_args)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return DatabaseManager(
        database_url=resolved_database_url,
        engine=engine,
        session_factory=session_factory,
        data_dir=resolved_data_dir,
        export_dir=export_dir,
    )


def init_database(db: DatabaseManager) -> None:
    Base.metadata.create_all(bind=db.engine)
    if db.database_url.startswith("sqlite"):
        migrate_sqlite_schema(db.engine)


def migrate_sqlite_schema(engine: Engine) -> None:
    additions = {
        "app_settings": {
            "crawl_strategy": "TEXT NOT NULL DEFAULT 'broad_it_scan'",
            "crawl_terms": "JSON NOT NULL DEFAULT '[]'",
            "listing_page_limit": "INTEGER NOT NULL DEFAULT 0",
            "detail_refetch_hours": "INTEGER NOT NULL DEFAULT 24",
            "ai_enrichment_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "ai_provider": "TEXT NOT NULL DEFAULT 'heuristic'",
            "ai_model": "TEXT NOT NULL DEFAULT ''",
            "browser_enabled": "BOOLEAN NOT NULL DEFAULT 1",
            "browser_headless": "BOOLEAN NOT NULL DEFAULT 1",
            "browser_timeout_seconds": "INTEGER NOT NULL DEFAULT 60",
        },
        "collection_runs": {
            "relevant_count": "INTEGER NOT NULL DEFAULT 0",
            "listing_page_count": "INTEGER NOT NULL DEFAULT 0",
            "detail_page_count": "INTEGER NOT NULL DEFAULT 0",
            "duplicate_skip_count": "INTEGER NOT NULL DEFAULT 0",
            "ai_enriched_count": "INTEGER NOT NULL DEFAULT 0",
            "raw_bytes_written": "INTEGER NOT NULL DEFAULT 0",
        },
        "job_postings": {
            "listing_snapshot_sha256": "TEXT NOT NULL DEFAULT ''",
            "detail_snapshot_sha256": "TEXT NOT NULL DEFAULT ''",
            "is_it_job": "BOOLEAN NOT NULL DEFAULT 1",
            "ai_provider": "TEXT NOT NULL DEFAULT ''",
            "ai_model": "TEXT NOT NULL DEFAULT ''",
            "ai_summary": "TEXT NOT NULL DEFAULT ''",
            "ai_relevance_reason": "TEXT NOT NULL DEFAULT ''",
            "ai_job_family": "TEXT NOT NULL DEFAULT ''",
            "ai_seniority": "TEXT NOT NULL DEFAULT ''",
            "ai_work_model": "TEXT NOT NULL DEFAULT ''",
            "ai_tech_stack": "JSON NOT NULL DEFAULT '[]'",
            "ai_requirements": "JSON NOT NULL DEFAULT '[]'",
            "ai_responsibilities": "JSON NOT NULL DEFAULT '[]'",
            "ai_benefits": "JSON NOT NULL DEFAULT '[]'",
            "detail_fetched_at": "DATETIME NULL",
            "enriched_at": "DATETIME NULL",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name in existing:
                    continue
                connection.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")
