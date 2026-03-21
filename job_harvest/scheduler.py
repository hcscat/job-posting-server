from __future__ import annotations

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from job_harvest.config import load_config
from job_harvest.runner import run_collection


def run_scheduler(config_path: str) -> None:
    config = load_config(config_path)
    if not config.schedule.enabled:
        raise SystemExit("schedule.enabled is false in the config file.")

    completed_runs = 0
    if config.schedule.run_on_start:
        execute_once(config_path)
        completed_runs += 1
        if reached_limit(config.schedule.max_runs, completed_runs):
            return

    while True:
        config = load_config(config_path)
        next_run = calculate_next_run(
            timezone_name=config.schedule.timezone,
            mode=config.schedule.mode,
            times=config.schedule.times,
            interval_hours=config.schedule.interval_hours,
        )
        sleep_until(next_run)
        execute_once(config_path)
        completed_runs += 1
        if reached_limit(config.schedule.max_runs, completed_runs):
            return


def execute_once(config_path: str) -> None:
    config = load_config(config_path)
    postings, run_dir = run_collection(config)
    print(f"[job_harvest] saved {len(postings)} postings to {run_dir}", flush=True)


def reached_limit(max_runs: int | None, completed_runs: int) -> bool:
    return max_runs is not None and completed_runs >= max_runs


def calculate_next_run(
    timezone_name: str,
    mode: str,
    times: list[str],
    interval_hours: int,
) -> datetime:
    zone = ZoneInfo(timezone_name)
    now = datetime.now(zone)

    if mode == "interval_hours":
        return now + timedelta(hours=interval_hours)

    candidates: list[datetime] = []
    for value in times:
        hour_text, minute_text = value.split(":", 1)
        candidate = now.replace(
            hour=int(hour_text),
            minute=int(minute_text),
            second=0,
            microsecond=0,
        )
        if candidate <= now:
            candidate += timedelta(days=1)
        candidates.append(candidate)
    return min(candidates)


def sleep_until(target: datetime) -> None:
    while True:
        now = datetime.now(target.tzinfo)
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 30))
