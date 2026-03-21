from __future__ import annotations

import argparse

import uvicorn

from job_harvest.config import build_queries, load_config
from job_harvest.runner import run_collection
from job_harvest.scheduler import run_scheduler
from job_harvest.server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and manage job postings.")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config file. Default: config.yaml",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the collector once from YAML config.")
    run_parser.set_defaults(command="run")

    schedule_parser = subparsers.add_parser("schedule", help="Run the collector on a schedule from YAML config.")
    schedule_parser.set_defaults(command="schedule")

    query_parser = subparsers.add_parser("show-queries", help="Print generated queries from YAML config.")
    query_parser.set_defaults(command="show-queries")

    serve_parser = subparsers.add_parser("serve", help="Start the web server.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    args = parser.parse_args()

    if args.command == "run":
        config = load_config(args.config)
        postings, run_dir = run_collection(config)
        print(f"[job_harvest] saved {len(postings)} postings to {run_dir}")
        return

    if args.command == "schedule":
        run_scheduler(args.config)
        return

    if args.command == "show-queries":
        config = load_config(args.config)
        for query in build_queries(config.criteria, config.search.queries):
            print(query)
        return

    if args.reload:
        uvicorn.run(
            "job_harvest.server:create_app",
            host=args.host,
            port=args.port,
            reload=True,
            factory=True,
        )
        return

    uvicorn.run(create_app(), host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
