import json
import unittest

from job_harvest.browser_collectors import (
    parse_blind_anchor_rows,
    parse_jobplanet_jobs_payload,
    parse_rocketpunch_jobs_payload,
)


class BrowserCollectorsTest(unittest.TestCase):
    def test_parse_jobplanet_jobs_payload(self) -> None:
        body = json.dumps(
            {
                "data": {
                    "search_result": {
                        "meta": {"total": 75},
                        "jobs": [
                            {
                                "id": 1311744,
                                "company": {"name": "Example Corp", "city_name": "Seoul"},
                                "recruitment_text": ["경력 3년 이상"],
                                "jd": {
                                    "title": "Backend Engineer",
                                    "created_at": "2026-03-20",
                                    "cities": [{"name": "Seoul"}],
                                    "job_type": {"name": "정규직"},
                                },
                            }
                        ],
                    }
                }
            },
            ensure_ascii=False,
        )

        hits, total_pages = parse_jobplanet_jobs_payload(
            body=body,
            source_query="backend",
            discovered_at="2026-03-20T00:00:00+00:00",
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(total_pages, 2)
        self.assertEqual(hits[0].site_key, "jobplanet")
        self.assertIn("posting_ids", hits[0].url)
        self.assertEqual(hits[0].company, "Example Corp")
        self.assertEqual(hits[0].location, "Seoul")

    def test_parse_rocketpunch_jobs_payload(self) -> None:
        body = json.dumps(
            {
                "totalItems": 60,
                "itemSize": 50,
                "items": [
                    {
                        "jobId": 158375,
                        "title": "Data Engineer",
                        "description": "Build ETL pipelines",
                        "companyName": "Rocket Data",
                        "workType": "FULL_TIME",
                        "seniorities": ["junior", "mid"],
                    }
                ],
            }
        )

        hits, total_pages = parse_rocketpunch_jobs_payload(
            body=body,
            source_query="data engineer",
            discovered_at="2026-03-20T00:00:00+00:00",
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(total_pages, 2)
        self.assertEqual(hits[0].site_key, "rocketpunch")
        self.assertIn("jobId=158375", hits[0].url)
        self.assertEqual(hits[0].company, "Rocket Data")

    def test_parse_blind_anchor_rows(self) -> None:
        hits = parse_blind_anchor_rows(
            rows=[
                {
                    "href": "https://www.teamblind.com/jobs/305253011",
                    "text": "Frontend Engineer\nExample Corp\nSeoul, KR",
                }
            ],
            source_query="__browser_all__",
            discovered_at="2026-03-20T00:00:00+00:00",
            term_filters=["frontend"],
        )

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].site_key, "blind")
        self.assertEqual(hits[0].search_title, "Frontend Engineer")
        self.assertEqual(hits[0].company, "Example Corp")
        self.assertEqual(hits[0].location, "Seoul, KR")


if __name__ == "__main__":
    unittest.main()
