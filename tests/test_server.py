import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from job_harvest.db_models import CollectionRunRecord, JobPostingRecord, utcnow
from job_harvest.server import create_app


def _mojibake(text: str) -> str:
    return text.encode("utf-8").decode("latin1")


class ServerTest(unittest.TestCase):
    def test_pages_settings_and_locale(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(data_dir=temp_dir)
            with TestClient(app) as client:
                dashboard = client.get("/")
                self.assertEqual(dashboard.status_code, 200)
                self.assertNotIn("run-now-button", dashboard.text)

                english_dashboard = client.get("/?lang=en")
                self.assertEqual(english_dashboard.status_code, 200)
                self.assertIn("Job Posting Server", english_dashboard.text)

                jobs_page = client.get("/jobs?lang=ko")
                self.assertEqual(jobs_page.status_code, 200)
                self.assertIn("job-detail-drawer", jobs_page.text)
                self.assertIn("job-detail-row", jobs_page.text)
                self.assertIn("사람인", jobs_page.text)

                settings_page = client.get("/settings?lang=ko")
                self.assertEqual(settings_page.status_code, 200)
                self.assertIn("사람인", settings_page.text)
                self.assertEqual(client.get("/health").status_code, 200)

                settings = client.get("/api/settings").json()
                settings["site_keys"] = ["saramin", "jobkorea"]
                settings["crawl_terms"] = ["frontend", "backend"]
                settings["ai_provider"] = "heuristic"
                settings["ai_model"] = ""
                settings["browser_enabled"] = True
                settings["browser_headless"] = True
                settings["browser_timeout_seconds"] = 45

                response = client.put("/api/settings", json=settings)
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["site_keys"], ["saramin", "jobkorea"])
                self.assertEqual(payload["crawl_terms"], ["frontend", "backend"])
                self.assertEqual(payload["ai_provider"], "heuristic")
                self.assertTrue(payload["browser_enabled"])
                self.assertTrue(payload["browser_headless"])
                self.assertEqual(payload["browser_timeout_seconds"], 45)

                interpreted = client.post(
                    "/api/settings/interpret",
                    json={
                        "text": "Saramin and JobPlanet frontend React jobs in Seoul only",
                        "base_payload": payload,
                    },
                )
                self.assertEqual(interpreted.status_code, 200)
                interpreted_payload = interpreted.json()["payload"]
                self.assertIn("saramin", interpreted_payload["site_keys"])
                self.assertIn("jobplanet", interpreted_payload["site_keys"])
                self.assertIn("Seoul", interpreted_payload["locations"])

    def test_run_job_and_raw_detail_routes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(data_dir=temp_dir)
            db = app.state.settings_service._db
            raw_store = app.state.raw_store

            listing_snapshot = raw_store.store_text(
                category="listing",
                url="https://example.com/jobs",
                text="<html><body>listing snapshot</body></html>",
            )
            detail_snapshot = raw_store.store_text(
                category="detail",
                url="https://example.com/jobs/1",
                text="<html><body>detail snapshot</body></html>",
            )

            export_dir = Path(temp_dir) / "exports" / "runs" / "seed-run"
            export_dir.mkdir(parents=True, exist_ok=True)

            with db.session_factory() as session:
                run = CollectionRunRecord(
                    triggered_by="manual",
                    status="success",
                    message="seeded run",
                    unique_hit_count=1,
                    relevant_count=1,
                    detail_page_count=1,
                    raw_bytes_written=detail_snapshot.byte_size,
                    export_path=str(export_dir),
                    started_at=utcnow(),
                    finished_at=utcnow(),
                )
                session.add(run)
                session.commit()
                session.refresh(run)

                job = JobPostingRecord(
                    latest_run_id=run.id,
                    normalized_url="https://example.com/jobs/1",
                    url="https://example.com/jobs/1",
                    site_key="saramin",
                    site_name="Saramin",
                    source_query="frontend",
                    title="Frontend Engineer",
                    search_title="Frontend Engineer",
                    company="Example Co",
                    location="Seoul",
                    employment_type="full-time",
                    experience_level="3 years",
                    status_code=200,
                    listing_snapshot_sha256=listing_snapshot.sha256_hex,
                    detail_snapshot_sha256=detail_snapshot.sha256_hex,
                    is_it_job=True,
                    ai_provider="heuristic",
                    ai_summary="Frontend role for product development.",
                    ai_job_family="frontend",
                    ai_tech_stack=["React", "TypeScript"],
                    raw_payload={"source": "seed"},
                    detail_fetched_at=utcnow(),
                    first_seen_at=utcnow(),
                    last_seen_at=utcnow(),
                    seen_count=1,
                )
                session.add(job)
                session.commit()

            (export_dir / "all_postings.json").write_text(
                json.dumps(
                    [
                        {
                            "site_key": "saramin",
                            "site_name": "Saramin",
                            "normalized_url": "https://example.com/jobs/1",
                            "url": "https://example.com/jobs/1",
                            "title": "Frontend Engineer",
                            "company": "Example Co",
                            "location": "Seoul",
                            "status_code": 200,
                            "is_it_job": True,
                            "listing_snapshot_sha256": listing_snapshot.sha256_hex,
                            "detail_snapshot_sha256": detail_snapshot.sha256_hex,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (export_dir / "raw_manifest.json").write_text(
                json.dumps(
                    [
                        {
                            "site_key": "saramin",
                            "site_name": "Saramin",
                            "normalized_url": "https://example.com/jobs/1",
                            "url": "https://example.com/jobs/1",
                            "title": "Frontend Engineer",
                            "status_code": 200,
                            "is_it_job": True,
                            "listing_snapshot_sha256": listing_snapshot.sha256_hex,
                            "detail_snapshot_sha256": detail_snapshot.sha256_hex,
                            "detail_fetched_at": utcnow().isoformat(),
                            "enriched_at": utcnow().isoformat(),
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with TestClient(app) as client:
                run_response = client.get("/api/runs/1")
                self.assertEqual(run_response.status_code, 200)
                self.assertEqual(len(run_response.json()["postings"]), 1)

                job_response = client.get("/api/jobs/1")
                self.assertEqual(job_response.status_code, 200)
                self.assertEqual(job_response.json()["title"], "Frontend Engineer")

                raw_response = client.get(f"/api/raw/detail/{detail_snapshot.sha256_hex}")
                self.assertEqual(raw_response.status_code, 200)
                self.assertIn("detail snapshot", raw_response.json()["text"])

                self.assertEqual(client.get("/runs/1").status_code, 200)
                self.assertEqual(client.get("/jobs/1").status_code, 200)
                self.assertEqual(
                    client.get(f"/raw/detail/{detail_snapshot.sha256_hex}").status_code,
                    200,
                )

    def test_api_job_text_cleanup_and_description_fallback(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(data_dir=temp_dir)
            db = app.state.settings_service._db

            with db.session_factory() as session:
                job = JobPostingRecord(
                    normalized_url="https://example.com/jobs/data-platform",
                    url="https://example.com/jobs/data-platform",
                    site_key="blind",
                    site_name="Blind",
                    source_query="data",
                    title=_mojibake("데이터 엔지니어"),
                    search_title=_mojibake("데이터 엔지니어"),
                    company=_mojibake("예시 회사"),
                    location=_mojibake("서울"),
                    employment_type="full-time",
                    experience_level="5 years",
                    summary=_mojibake("데이터 엔지니어 · Python"),
                    description="",
                    extraction_method="search-result",
                    status_code=403,
                    is_it_job=True,
                    ai_provider="heuristic",
                    ai_summary=_mojibake("원격 데이터 파이프라인 개발"),
                    ai_requirements=[_mojibake("Python"), _mojibake("Airflow")],
                    ai_responsibilities=[_mojibake("데이터 파이프라인 구축")],
                    ai_benefits=[_mojibake("교육 지원")],
                    raw_payload={
                        "headline": _mojibake("데이터 · 분석"),
                        "highlights": [_mojibake("복지 · 교육")],
                    },
                    first_seen_at=utcnow(),
                    last_seen_at=utcnow(),
                    seen_count=1,
                )
                session.add(job)
                session.commit()

            with TestClient(app) as client:
                list_response = client.get("/api/jobs?site=blind")
                self.assertEqual(list_response.status_code, 200)
                list_payload = list_response.json()
                self.assertEqual(list_payload["total"], 1)
                self.assertEqual(list_payload["items"][0]["title"], "데이터 엔지니어")
                self.assertEqual(list_payload["items"][0]["summary"], "데이터 엔지니어 · Python")
                self.assertIn("원격 데이터 파이프라인 개발", list_payload["items"][0]["description"])

                detail_response = client.get("/api/jobs/1")
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()
                self.assertEqual(detail_payload["title"], "데이터 엔지니어")
                self.assertEqual(detail_payload["summary"], "데이터 엔지니어 · Python")
                self.assertEqual(detail_payload["ai_summary"], "원격 데이터 파이프라인 개발")
                self.assertEqual(detail_payload["raw_payload"]["headline"], "데이터 · 분석")
                self.assertEqual(detail_payload["raw_payload"]["highlights"], ["복지 · 교육"])
                self.assertIn("Responsibilities", detail_payload["description"])
                self.assertIn("데이터 파이프라인 구축", detail_payload["description"])
                self.assertIn("Requirements", detail_payload["description"])
                self.assertIn("Benefits", detail_payload["description"])
                self.assertIn("Detail page capture was limited", detail_payload["description"])


if __name__ == "__main__":
    unittest.main()
