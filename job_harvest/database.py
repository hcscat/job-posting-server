from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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
