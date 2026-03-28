import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from job_harvest.db_models import CollectionRunRecord, JobPostingRecord, utcnow
from job_harvest.server import create_app


class ServerTest(unittest.TestCase):
    def test_pages_settings_and_locale(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(data_dir=temp_dir)
            with TestClient(app) as client:
                dashboard = client.get("/")
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn("채용 공고 서버", dashboard.text)
                self.assertNotIn("run-now-button", dashboard.text)

                english_dashboard = client.get("/?lang=en")
                self.assertEqual(english_dashboard.status_code, 200)
                self.assertIn("Job Posting Server", english_dashboard.text)

                jobs_page = client.get("/jobs")
                self.assertEqual(jobs_page.status_code, 200)
                self.assertIn("job-detail-drawer", jobs_page.text)

                self.assertEqual(client.get("/settings").status_code, 200)
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
                session.refresh(job)

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
                self.assertEqual(client.get(f"/raw/detail/{detail_snapshot.sha256_hex}").status_code, 200)


if __name__ == "__main__":
    unittest.main()
