import unittest

from job_harvest.config import build_config
from job_harvest.models import JobPosting
from job_harvest.query_planner import build_site_query_plan
from job_harvest.runner import is_relevant_posting


class QueryPlannerTest(unittest.TestCase):
    def test_site_query_plan_uses_supported_filters_only(self) -> None:
        config = build_config(
            {
                "criteria": {
                    "roles": ["프론트엔드 개발자"],
                    "skills": ["React"],
                    "locations": ["서울"],
                    "welfare": ["식대 지원"],
                }
            }
        )

        blind_plan = build_site_query_plan(
            site_key="blind",
            criteria=config.criteria,
            crawl_strategy="query_search",
            crawl_terms=config.search.crawl_terms,
            manual_queries=[],
        )

        combined = " ".join(blind_plan.queries)
        self.assertIn("React", combined)
        self.assertIn("서울", combined)
        self.assertNotIn("식대 지원", combined)
        self.assertIn("skills", blind_plan.active_fields)
        self.assertIn("locations", blind_plan.active_fields)
        self.assertNotIn("welfare", blind_plan.active_fields)

    def test_query_search_merges_manual_queries_with_structured_filters(self) -> None:
        config = build_config(
            {
                "search": {
                    "crawl_strategy": "query_search",
                    "queries": ["python backend"],
                },
                "criteria": {
                    "locations": ["Seoul"],
                    "skills": ["FastAPI"],
                },
            }
        )

        plan = build_site_query_plan(
            site_key="linkedin",
            criteria=config.criteria,
            crawl_strategy=config.search.crawl_strategy,
            crawl_terms=config.search.crawl_terms,
            manual_queries=config.search.queries,
        )

        combined = " ".join(plan.queries)
        self.assertIn("python backend", combined)
        self.assertIn("Seoul", combined)
        self.assertIn("FastAPI", combined)

    def test_text_query_only_fields_do_not_activate_native_site_filters(self) -> None:
        config = build_config(
            {
                "criteria": {
                    "skills": ["Python"],
                }
            }
        )

        plan = build_site_query_plan(
            site_key="remember",
            criteria=config.criteria,
            crawl_strategy="broad_it_scan",
            crawl_terms=config.search.crawl_terms,
            manual_queries=[],
        )

        self.assertEqual(plan.active_fields, ())
        self.assertTrue(any("Python" in query for query in plan.queries))

    def test_broad_scan_respects_filters_when_user_configured_them(self) -> None:
        config = build_config(
            {
                "search": {
                    "crawl_strategy": "broad_it_scan",
                },
                "criteria": {
                    "locations": ["서울"],
                    "skills": ["Python"],
                },
            }
        )

        posting = JobPosting(
            site_key="saramin",
            site_name="Saramin",
            source_query="python",
            discovered_at="2026-04-19T00:00:00+00:00",
            url="https://example.com/jobs/1",
            normalized_url="https://example.com/jobs/1",
            title="Java Engineer",
            company="Example",
            location="부산",
            description="Java Spring service role",
            is_it_job=True,
        )
        self.assertFalse(is_relevant_posting(posting, config))

        posting.location = "서울"
        posting.ai_tech_stack = ["Python", "FastAPI"]
        posting.description = "Python FastAPI backend service role"
        self.assertTrue(is_relevant_posting(posting, config))


if __name__ == "__main__":
    unittest.main()
