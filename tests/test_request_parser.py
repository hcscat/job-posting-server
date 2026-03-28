import unittest

from job_harvest.request_parser import interpret_collection_request
from job_harvest.schemas import SettingsPayload


class RequestParserTest(unittest.TestCase):
    def test_interpret_collection_request_with_heuristics(self) -> None:
        current = SettingsPayload()
        interpretation = interpret_collection_request(
            "사람인, 잡플래닛, 블라인드에서 서울 프론트엔드 개발자 React 공고만 찾아줘. 신입 또는 3년 이하, 정규직 기준.",
            current,
        )

        payload = interpretation.payload
        self.assertEqual(interpretation.provider, "heuristic")
        self.assertIn("saramin", payload.site_keys)
        self.assertIn("jobplanet", payload.site_keys)
        self.assertIn("blind", payload.site_keys)
        self.assertIn("서울", payload.locations)
        self.assertIn("프론트엔드", payload.roles)
        self.assertIn("React", payload.keywords)
        self.assertIn("정규직", payload.employment_types)
        self.assertTrue(any(value in payload.experience_levels for value in ["신입", "3년 이하", "3년"]))
        self.assertIn(payload.crawl_strategy, {"query_search", "broad_it_scan"})


if __name__ == "__main__":
    unittest.main()
