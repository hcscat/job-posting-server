import unittest

from job_harvest.ai_enrichment import HeuristicEnricher, apply_enrichment
from job_harvest.models import JobPosting


class EnrichmentTest(unittest.TestCase):
    def test_heuristic_enricher_marks_it_job(self) -> None:
        posting = JobPosting(
            site_key="test",
            site_name="Test",
            source_query="개발",
            discovered_at="2026-03-28T00:00:00+00:00",
            url="https://example.com/jobs/1",
            normalized_url="https://example.com/jobs/1",
            title="Backend Engineer",
            summary="Python FastAPI backend service development",
            description=(
                "주요업무: Python FastAPI 백엔드 개발\n"
                "자격요건: Python, SQL, AWS 경험\n"
                "복지: 재택근무, 장비 지원"
            ),
        )

        enrichment = HeuristicEnricher().enrich(posting)
        apply_enrichment(posting, enrichment)

        self.assertTrue(posting.is_it_job)
        self.assertIn("python", posting.ai_tech_stack)
        self.assertTrue(posting.ai_summary)
        self.assertTrue(posting.ai_requirements)


if __name__ == "__main__":
    unittest.main()
