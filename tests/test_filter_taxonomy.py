import unittest

from job_harvest.filter_taxonomy import (
    ALL_STANDARD_FILTER_FIELDS,
    SITE_FILTER_SUPPORT,
    get_site_filter_support,
    get_uncovered_sites,
)


class FilterTaxonomyTest(unittest.TestCase):
    def test_all_default_sites_are_covered(self) -> None:
        self.assertEqual(get_uncovered_sites(), set())

    def test_all_standardized_fields_are_declared(self) -> None:
        invalid_fields = {
            capability.standardized_field
            for capabilities in SITE_FILTER_SUPPORT.values()
            for capability in capabilities
            if capability.standardized_field not in ALL_STANDARD_FILTER_FIELDS
        }
        self.assertEqual(invalid_fields, set())

    def test_site_lookup_is_case_insensitive(self) -> None:
        capabilities = get_site_filter_support("Saramin")
        self.assertGreater(len(capabilities), 0)
        self.assertEqual(capabilities[0].standardized_field, "keywords")


if __name__ == "__main__":
    unittest.main()
