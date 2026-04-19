import json
import unittest
from datetime import timedelta
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
                settings["industries"] = ["핀테크"]
                settings["skills"] = ["React", "TypeScript"]
                settings["workplace_types"] = ["원격"]
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
                self.assertEqual(payload["industries"], ["핀테크"])
                self.assertEqual(payload["skills"], ["React", "TypeScript"])
                self.assertEqual(payload["workplace_types"], ["원격"])
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

    def test_api_jobs_supports_recommended_only_and_profile_fit_sort(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(data_dir=temp_dir)
            db = app.state.settings_service._db
            now = utcnow()

            with db.session_factory() as session:
                high_fit_job = JobPostingRecord(
                    normalized_url="https://example.com/jobs/java-backoffice",
                    url="https://example.com/jobs/java-backoffice",
                    site_key="saramin",
                    site_name="Saramin",
                    source_query="Java Spring 업무 시스템 개발자",
                    title="Java Spring 업무 시스템 개발자",
                    search_title="Java Spring 업무 시스템 개발자",
                    company="Example SI",
                    location="서울",
                    employment_type="정규직",
                    experience_level="3년 이상",
                    education_level="무관",
                    summary="공공 백오피스 운영개발 포지션",
                    description="공공 백오피스 운영개발과 관리자 화면 개발을 수행합니다.",
                    status_code=200,
                    is_it_job=True,
                    ai_provider="heuristic",
                    ai_summary="Java Spring 기반 업무 시스템 백엔드/운영개발 포지션",
                    ai_relevance_reason="Java, Spring, 백오피스, 운영개발 경험과 직접 맞닿아 있습니다.",
                    ai_job_family="backend",
                    ai_tech_stack=["Java", "Spring", "MyBatis", "Oracle"],
                    ai_requirements=["Java", "Spring", "업무 시스템"],
                    ai_responsibilities=["백오피스 운영개발", "관리자 화면 연계"],
                    ai_benefits=["유연근무"],
                    first_seen_at=now - timedelta(days=3),
                    last_seen_at=now - timedelta(days=2),
                    seen_count=1,
                )
                low_fit_job = JobPostingRecord(
                    normalized_url="https://example.com/jobs/data-scientist",
                    url="https://example.com/jobs/data-scientist",
                    site_key="linkedin",
                    site_name="LinkedIn",
                    source_query="data scientist",
                    title="Data Scientist",
                    search_title="Data Scientist",
                    company="ML Lab",
                    location="서울",
                    employment_type="정규직",
                    experience_level="무관",
                    education_level="석사 이상",
                    summary="머신러닝 모델 개발 및 실험 자동화",
                    description="머신러닝 모델 개발과 데이터 분석 전담 포지션",
                    status_code=200,
                    is_it_job=True,
                    ai_provider="heuristic",
                    ai_summary="머신러닝 모델링 중심 포지션",
                    ai_relevance_reason="데이터 사이언스와 AI 리서치 성격이 강합니다.",
                    ai_job_family="data",
                    ai_tech_stack=["Python", "TensorFlow"],
                    ai_requirements=["머신러닝", "Python"],
                    ai_responsibilities=["모델 개발", "실험 자동화"],
                    ai_benefits=["원격근무"],
                    first_seen_at=now - timedelta(days=1),
                    last_seen_at=now,
                    seen_count=1,
                )
                session.add(high_fit_job)
                session.add(low_fit_job)
                session.commit()
                session.refresh(high_fit_job)

            with TestClient(app) as client:
                profile_response = client.get("/api/profile")
                self.assertEqual(profile_response.status_code, 200)
                self.assertIn("Java", profile_response.json()["strong_skills"])

                fit_sorted = client.get("/api/jobs?sort=profile_fit")
                self.assertEqual(fit_sorted.status_code, 200)
                fit_items = fit_sorted.json()["items"]
                self.assertEqual(fit_items[0]["title"], "Java Spring 업무 시스템 개발자")
                self.assertIn("profile_fit_score", fit_items[0])
                self.assertIn("profile_fit_level", fit_items[0])
                self.assertTrue(fit_items[0]["profile_fit_reasons"])

                latest_sorted = client.get("/api/jobs?sort=latest")
                self.assertEqual(latest_sorted.status_code, 200)
                latest_items = latest_sorted.json()["items"]
                self.assertEqual(latest_items[0]["title"], "Data Scientist")

                recommended_only = client.get("/api/jobs?recommended_only=true&sort=profile_fit")
                self.assertEqual(recommended_only.status_code, 200)
                recommended_payload = recommended_only.json()
                self.assertEqual(recommended_payload["total"], 1)
                self.assertEqual(recommended_payload["items"][0]["title"], "Java Spring 업무 시스템 개발자")
                self.assertGreaterEqual(recommended_payload["items"][0]["profile_fit_score"], 50)

                detail_response = client.get(f"/api/jobs/{high_fit_job.id}")
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()
                self.assertGreaterEqual(detail_payload["profile_fit_score"], 50)
                self.assertIn("Java", detail_payload["profile_fit_highlights"])
                self.assertIn("공공 백오피스 운영개발과 관리자 화면 개발을 수행합니다.", detail_payload["description"])

    def test_jobs_page_renders_profile_fit_controls_and_datasets(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(data_dir=temp_dir)
            db = app.state.settings_service._db

            with db.session_factory() as session:
                session.add(
                    JobPostingRecord(
                        normalized_url="https://example.com/jobs/ui5",
                        url="https://example.com/jobs/ui5",
                        site_key="wanted",
                        site_name="Wanted",
                        source_query="SAP UI5 개발",
                        title="SAP UI5 운영개발",
                        search_title="SAP UI5 운영개발",
                        company="Enterprise App Co",
                        location="판교",
                        employment_type="정규직",
                        experience_level="5년 이상",
                        summary="SAP UI5/Fiori 기반 운영개발",
                        description="SAP UI5/Fiori 기반 운영개발과 유지보수",
                        status_code=200,
                        is_it_job=True,
                        ai_provider="heuristic",
                        ai_summary="SAP UI5/Fiori 운영개발 포지션",
                        ai_job_family="frontend",
                        ai_tech_stack=["JavaScript", "SAP UI5", "Fiori"],
                        ai_requirements=["SAP UI5", "JavaScript"],
                        ai_responsibilities=["운영개발"],
                        first_seen_at=utcnow(),
                        last_seen_at=utcnow(),
                        seen_count=1,
                    )
                )
                session.commit()

            with TestClient(app) as client:
                response = client.get("/jobs?lang=ko&recommended_only=true&sort=profile_fit")
                self.assertEqual(response.status_code, 200)
                self.assertIn('name="recommended_only"', response.text)
                self.assertIn('value="profile_fit" selected', response.text)
                self.assertIn("job-detail-fit-badge", response.text)
                self.assertIn("data-fit-score=", response.text)
                self.assertIn("data-fit-reasons=", response.text)
                self.assertIn("사람인", response.text)


if __name__ == "__main__":
    unittest.main()
