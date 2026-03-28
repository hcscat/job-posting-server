from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from hashlib import sha1
from pathlib import Path

from job_harvest.models import JobPosting


def persist_run(
    output_dir: Path,
    postings: list[JobPosting],
    queries: list[str],
    config_source: str,
    store_html: bool,
    html_by_url: dict[str, str],
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / "runs" / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    if store_html and html_by_url:
        html_dir = run_dir / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        for posting in postings:
            html = html_by_url.get(posting.normalized_url, "")
            if not html:
                continue
            file_name = f"{sha1(posting.normalized_url.encode('utf-8')).hexdigest()}.html"
            html_path = html_dir / file_name
            html_path.write_text(html, encoding="utf-8")
            posting.html_path = str(html_path)

    rows = [posting.to_dict() for posting in postings]
    write_json(run_dir / "results.json", rows)
    write_csv(run_dir / "results.csv", rows)
    write_summary(run_dir / "summary.md", postings, queries, config_source)
    return run_dir


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "site_name",
        "title",
        "company",
        "location",
        "employment_type",
        "experience_level",
        "education_level",
        "date_posted",
        "valid_through",
        "url",
        "search_title",
        "search_snippet",
        "summary",
        "source_query",
        "discovered_at",
        "detail_fetched_at",
        "enriched_at",
        "pub_date",
        "extraction_method",
        "status_code",
        "html_path",
        "tags",
        "is_it_job",
        "ai_provider",
        "ai_model",
        "ai_summary",
        "ai_relevance_reason",
        "ai_job_family",
        "ai_seniority",
        "ai_work_model",
        "ai_tech_stack",
        "ai_requirements",
        "ai_responsibilities",
        "ai_benefits",
        "listing_snapshot_sha256",
        "detail_snapshot_sha256",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_summary(
    path: Path,
    postings: list[JobPosting],
    queries: list[str],
    config_source: str,
) -> None:
    counts = Counter(posting.site_name for posting in postings)
    lines = [
        "# Job Harvest Summary",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Config source: {config_source}",
        f"- Total postings: {len(postings)}",
        "",
        "## Queries",
        "",
    ]
    for query in queries:
        lines.append(f"- {query}")

    lines.extend(["", "## Site Counts", ""])
    if counts:
        for site_name, count in counts.most_common():
            lines.append(f"- {site_name}: {count}")
    else:
        lines.append("- No postings matched the current filters.")

    lines.extend(["", "## Top Results Preview", ""])
    if postings:
        for posting in postings[:50]:
            title = posting.title or posting.search_title or "(제목 없음)"
            company = posting.company or "회사 미확인"
            location = posting.location or "지역 미확인"
            family = posting.ai_job_family or "unclassified"
            lines.append(f"- [{posting.site_name}] {title} | {company} | {location} | {family} | {posting.url}")
    else:
        lines.append("- No postings saved in this run.")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
