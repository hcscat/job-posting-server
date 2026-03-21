import unittest
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from job_harvest.server import create_app


class ServerTest(unittest.TestCase):
    def test_pages_and_settings_api(self) -> None:
        with TemporaryDirectory() as temp_dir:
            app = create_app(data_dir=temp_dir)
            with TestClient(app) as client:
                self.assertEqual(client.get("/health").status_code, 200)
                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.get("/settings").status_code, 200)
                self.assertEqual(client.get("/jobs").status_code, 200)

                settings = client.get("/api/settings").json()
                settings["site_keys"] = ["saramin", "jobkorea"]
                settings["schedule_enabled"] = True
                settings["schedule_mode"] = "interval_hours"
                settings["schedule_interval_hours"] = 6

                response = client.put("/api/settings", json=settings)
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["site_keys"], ["saramin", "jobkorea"])
                self.assertTrue(payload["schedule_enabled"])
                self.assertEqual(payload["schedule_interval_hours"], 6)


if __name__ == "__main__":
    unittest.main()
