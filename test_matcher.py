"""Tests for the conservative SNAP prescreen matcher."""

from __future__ import annotations

import unittest
from pathlib import Path

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
    }
    profile.update(overrides)
    return profile


class SnapMatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.programs = load_programs(str(PROGRAMS_PATH))

    def test_florida_household_of_three_at_27000_is_possible_match(self) -> None:
        matches = find_matches(make_profile(), self.programs)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["program_id"], "florida-snap")
        self.assertEqual(matches[0]["status"], "possible_match")
        self.assertTrue(matches[0]["needs_verification"])

    def test_florida_household_of_three_at_60000_is_not_returned(self) -> None:
        matches = find_matches(
            make_profile(annual_income=60000),
            self.programs,
        )

        self.assertEqual(matches, [])

    def test_non_florida_profile_is_not_returned(self) -> None:
        matches = find_matches(make_profile(zip_code="10001"), self.programs)

        self.assertEqual(matches, [])

    def test_household_of_nine_uses_additional_person_amount(self) -> None:
        at_limit = find_matches(
            make_profile(household_size=9, annual_income=119300),
            self.programs,
        )
        above_limit = find_matches(
            make_profile(household_size=9, annual_income=119301),
            self.programs,
        )

        self.assertEqual(len(at_limit), 1)
        self.assertIn("$119,300", at_limit[0]["matched_reasons"][1])
        self.assertEqual(above_limit, [])

    def test_missing_required_profile_data_is_not_returned(self) -> None:
        for missing_field in ("zip_code", "annual_income", "household_size"):
            with self.subTest(missing_field=missing_field):
                profile = make_profile()
                profile.pop(missing_field)
                self.assertEqual(find_matches(profile, self.programs), [])


if __name__ == "__main__":
    unittest.main()
