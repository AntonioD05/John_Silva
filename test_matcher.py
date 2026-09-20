"""Tests for the conservative SNAP prescreen matcher."""

from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from unittest import mock

from matcher import find_matches, load_programs


PROGRAMS_PATH = Path(__file__).with_name("programs.json")


def make_profile(**overrides: object) -> dict:
    """Return a profile using exactly the field names emitted by app.py."""
    profile = {
        "zip_code": "32601",
        "age": 29,
        "annual_income": 27000,
        "household_size": 3,
        "dependent_children": 2,
        "student": False,
        "employment_status": "Employed",
        "disability": False,
        "veteran": False,
        "pregnant_postpartum_or_breastfeeding": False,
        "has_child_under_5": False,
    }
    profile.update(overrides)
    return profile


class SnapMatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.programs = load_programs(str(PROGRAMS_PATH))

    def snap_matches(self, profile: dict) -> list[dict]:
        return [
            match
            for match in find_matches(profile, self.programs)
            if match["program_id"] == "florida-snap"
        ]

    def test_florida_household_of_three_at_27000_is_possible_match(self) -> None:
        matches = self.snap_matches(make_profile())

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["program_id"], "florida-snap")
        self.assertEqual(matches[0]["status"], "possible_match")
        self.assertTrue(matches[0]["needs_verification"])

    def test_florida_household_of_three_at_60000_is_not_returned(self) -> None:
        matches = self.snap_matches(make_profile(annual_income=60000))

        self.assertEqual(matches, [])

    def test_non_florida_profile_is_not_returned(self) -> None:
        matches = find_matches(make_profile(zip_code="10001"), self.programs)

        self.assertEqual(matches, [])

    def test_household_of_nine_uses_additional_person_amount(self) -> None:
        at_limit = self.snap_matches(
            make_profile(household_size=9, annual_income=119300)
        )
        above_limit = self.snap_matches(
            make_profile(household_size=9, annual_income=119301)
        )

        self.assertEqual(len(at_limit), 1)
        self.assertIn("$119,300", at_limit[0]["matched_reasons"][1])
        self.assertEqual(above_limit, [])

    def test_missing_required_profile_data_is_not_returned(self) -> None:
        for missing_field in ("zip_code", "annual_income", "household_size"):
            with self.subTest(missing_field=missing_field):
                profile = make_profile()
                profile.pop(missing_field)
                self.assertEqual(self.snap_matches(profile), [])


class WicMatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.programs = load_programs(str(PROGRAMS_PATH))

    def wic_matches(self, **overrides: object) -> list[dict]:
        return [
            match
            for match in find_matches(make_profile(**overrides), self.programs)
            if match["program_id"] == "florida-wic"
        ]

    def test_child_under_five_below_income_limit_returns_wic(self) -> None:
        matches = self.wic_matches(has_child_under_5=True, annual_income=50000)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["status"], "possible_match")

    def test_pregnant_postpartum_or_breastfeeding_below_limit_returns_wic(self) -> None:
        matches = self.wic_matches(
            pregnant_postpartum_or_breastfeeding=True,
            annual_income=50000,
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["status"], "possible_match")

    def test_neither_demographic_condition_does_not_return_wic(self) -> None:
        self.assertEqual(self.wic_matches(annual_income=27000), [])

    def test_income_above_limit_does_not_return_wic(self) -> None:
        matches = self.wic_matches(has_child_under_5=True, annual_income=50543)

        self.assertEqual(matches, [])

    def test_household_larger_than_eight_is_unresolved_without_threshold(self) -> None:
        matches = self.wic_matches(
            has_child_under_5=True,
            household_size=9,
            annual_income=1,
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["status"], "possible_match")
        self.assertEqual(len(matches[0]["matched_reasons"]), 2)
        self.assertTrue(
            any(
                "stops at a household size of eight" in note
                and "not invented or extrapolated" in note
                for note in matches[0]["needs_verification"]
            )
        )

    def test_any_truthy_passes_when_other_field_is_missing(self) -> None:
        profile = make_profile(has_child_under_5=True, annual_income=50000)
        profile.pop("pregnant_postpartum_or_breastfeeding")

        matches = [
            match
            for match in find_matches(profile, self.programs)
            if match["program_id"] == "florida-wic"
        ]

        self.assertEqual(len(matches), 1)

    def test_any_truthy_is_unresolved_when_no_true_and_one_field_missing(self) -> None:
        profile = make_profile(annual_income=27000)
        profile.pop("pregnant_postpartum_or_breastfeeding")

        matches = [
            match
            for match in find_matches(profile, self.programs)
            if match["program_id"] == "florida-wic"
        ]

        self.assertEqual(matches, [])

    def test_load_programs_rejects_invalid_any_truthy_fields(self) -> None:
        programs = json.loads(PROGRAMS_PATH.read_text(encoding="utf-8"))
        wic = next(program for program in programs if program["id"] == "florida-wic")
        demographic_rule = next(
            rule for rule in wic["rules"] if rule["operator"] == "any_truthy"
        )
        demographic_rule["fields"] = []

        invalid_json = io.StringIO(json.dumps(programs))
        with mock.patch.object(Path, "open", return_value=invalid_json):
            with self.assertRaisesRegex(ValueError, "any_truthy"):
                load_programs("invalid-programs.json")


class RemainingResourcesIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.programs = load_programs(str(PROGRAMS_PATH))

    def results_by_id(self, **overrides: object) -> dict[str, dict]:
        return {
            match["program_id"]: match
            for match in find_matches(make_profile(**overrides), self.programs)
        }

    def test_gainesville_veteran_with_child_under_five_returns_all_four(self) -> None:
        results = self.results_by_id(
            zip_code="32601",
            veteran=True,
            dependent_children=1,
            has_child_under_5=True,
            annual_income=60000,
        )
        expected_ids = {
            "alachua-county-veteran-services",
            "florida-kidcare",
            "alachua-county-social-services",
            "gainesville-housing-community-development",
        }

        for program_id in expected_ids:
            with self.subTest(program_id=program_id):
                self.assertIn(program_id, results)
                self.assertEqual(results[program_id]["status"], "possible_match")
        self.assertIsNone(results["alachua-county-veteran-services"]["apply_url"])
        self.assertIsNone(
            results["gainesville-housing-community-development"]["apply_url"]
        )

    def test_alachua_non_veteran_with_child_excludes_veteran_and_gainesville(self) -> None:
        results = self.results_by_id(
            zip_code="32615",
            veteran=False,
            dependent_children=1,
            has_child_under_5=False,
            annual_income=60000,
        )

        self.assertIn("florida-kidcare", results)
        self.assertIn("alachua-county-social-services", results)
        self.assertNotIn("alachua-county-veteran-services", results)
        self.assertNotIn("gainesville-housing-community-development", results)

    def test_florida_outside_alachua_with_child_returns_only_kidcare_locally(self) -> None:
        results = self.results_by_id(
            zip_code="33101",
            veteran=True,
            dependent_children=1,
            has_child_under_5=False,
            annual_income=60000,
        )

        self.assertIn("florida-kidcare", results)
        self.assertNotIn("alachua-county-veteran-services", results)
        self.assertNotIn("alachua-county-social-services", results)
        self.assertNotIn("gainesville-housing-community-development", results)

    def test_florida_with_zero_dependent_children_excludes_kidcare(self) -> None:
        results = self.results_by_id(
            zip_code="33101",
            dependent_children=0,
            has_child_under_5=False,
            annual_income=60000,
        )

        self.assertNotIn("florida-kidcare", results)


if __name__ == "__main__":
    unittest.main()
