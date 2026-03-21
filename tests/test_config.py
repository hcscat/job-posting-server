import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from job_harvest.config import build_queries, load_config


class ConfigTest(unittest.TestCase):
    def test_load_config_and_build_queries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text(
                """
output_dir: "./output"
criteria:
  roles:
    - "백엔드 개발자"
  keywords:
    - "Python"
    - "FastAPI"
  locations:
    - "서울"
  extra_terms:
    - "채용"
search:
  sites:
    - saramin
""".strip(),
                encoding="utf-8",
            )

            config = load_config(config_path)
            self.assertEqual(config.search.sites, ["saramin"])
            self.assertEqual(
                build_queries(config.criteria, []),
                ["백엔드 개발자 Python FastAPI 서울 채용"],
            )


if __name__ == "__main__":
    unittest.main()
