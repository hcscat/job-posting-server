from __future__ import annotations

import unittest
from datetime import datetime, timezone

from job_harvest.models import SearchHit
from job_harvest.runner import split_hits_for_detail_refresh


class RunnerTest(unittest.TestCase):
    def test_split_hits_for_detail_refresh_accepts_naive_timestamps(self) -> None:
        hit = SearchHit(
            site_key="blind",
            site_name="Blind",
            source_query="software engineer",
            discovered_at="2026-03-29T00:00:00+00:00",
            search_title="Software Engineer",
            url="https://www.teamblind.com/jobs/1",
            normalized_url="https://www.teamblind.com/jobs/1",
        )

        to_fetch, skipped = split_hits_for_detail_refresh(
            [hit],
            {hit.normalized_url: datetime.now()},
            detail_refetch_hours=24,
        )

        self.assertEqual(to_fetch, [])
        self.assertEqual(skipped, [hit])

    def test_split_hits_for_detail_refresh_keeps_old_entries(self) -> None:
        hit = SearchHit(
            site_key="blind",
            site_name="Blind",
            source_query="software engineer",
            discovered_at="2026-03-29T00:00:00+00:00",
            search_title="Software Engineer",
            url="https://www.teamblind.com/jobs/2",
            normalized_url="https://www.teamblind.com/jobs/2",
        )

        old_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        to_fetch, skipped = split_hits_for_detail_refresh(
            [hit],
            {hit.normalized_url: old_timestamp},
            detail_refetch_hours=24,
        )

        self.assertEqual(to_fetch, [hit])
        self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
