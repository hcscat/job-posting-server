import unittest

from bs4 import BeautifulSoup

from job_harvest.extract import extract_job_posting_from_json_ld


class ExtractTest(unittest.TestCase):
    def test_extract_job_posting_from_json_ld(self) -> None:
        html = """
        <html>
          <head>
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "@type": "JobPosting",
                "title": "Backend Engineer",
                "description": "<p>Python API development</p>",
                "datePosted": "2026-03-20",
                "validThrough": "2026-04-20",
                "employmentType": "FULL_TIME",
                "skills": ["Python", "FastAPI"],
                "hiringOrganization": {
                  "@type": "Organization",
                  "name": "Example Corp"
                },
                "jobLocation": {
                  "@type": "Place",
                  "address": {
                    "@type": "PostalAddress",
                    "addressCountry": "KR",
                    "addressRegion": "Seoul",
                    "addressLocality": "Gangnam-gu"
                  }
                }
              }
            </script>
          </head>
        </html>
        """

        soup = BeautifulSoup(html, "html.parser")
        posting = extract_job_posting_from_json_ld(soup)
        self.assertEqual(posting["title"], "Backend Engineer")
        self.assertEqual(posting["company"], "Example Corp")
        self.assertEqual(posting["location"], "KR, Seoul, Gangnam-gu")
        self.assertEqual(posting["employment_type"], "FULL_TIME")
        self.assertEqual(posting["tags"], ["Python", "FastAPI"])


if __name__ == "__main__":
    unittest.main()
