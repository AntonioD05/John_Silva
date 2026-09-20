"""Tests for Gemini guide constraints and deterministic fallbacks."""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest import mock

from ai_guide import (
    build_fallback_guide,
    generate_action_guide,
    generate_action_guide_with_status,
)


MATCHES = [
    {
        "program_id": "florida-snap",
        "name": "SNAP",
        "description": "Food assistance.",
        "matched_reasons": ["Reported income: $27,000."],
        "needs_verification": ["Student restrictions may apply."],
        "source_url": "https://source.example/snap",
        "apply_url": "https://apply.example/snap",
    },
    {
        "program_id": "local-support",
        "name": "Local Support",
        "description": "Local referrals.",
        "needs_verification": ["Availability must be confirmed."],
        "source_url": "https://source.example/local",
        "apply_url": None,
    },
]


class ActionGuideTests(unittest.TestCase):
    def test_fallback_preserves_ids_and_supports_all_languages(self) -> None:
        for language in ("English", "Spanish", "Haitian Creole"):
            with self.subTest(language=language):
                guide = build_fallback_guide(MATCHES, language)
                self.assertEqual(
                    [step["program_id"] for step in guide["steps"]],
                    ["florida-snap", "local-support"],
                )
                self.assertTrue(guide["introduction"])
                self.assertTrue(guide["reminder"])

    def test_known_programs_get_distinct_fallback_guidance(self) -> None:
        guide = build_fallback_guide(MATCHES, "English")
        self.assertIn("MyACCESS", guide["steps"][0]["action"])
        self.assertIn("student rules", guide["steps"][0]["question_to_ask"])
        self.assertNotEqual(
            guide["steps"][0]["question_to_ask"],
            guide["steps"][1]["question_to_ask"],
        )

    def test_missing_api_key_uses_fallback(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            guide = generate_action_guide(MATCHES, "English")

        self.assertEqual(guide, build_fallback_guide(MATCHES, "English"))

        _, used_fallback = generate_action_guide_with_status(MATCHES, "English")
        self.assertTrue(used_fallback)

    def test_valid_gemini_response_is_used_without_sending_urls_or_income(self) -> None:
        generated = {
            "introduction": "Suggested order.",
            "steps": [
                {
                    "program_id": "florida-snap",
                    "action": "Review the application requirements.",
                    "question_to_ask": "Do student restrictions apply?",
                },
                {
                    "program_id": "local-support",
                    "action": "Contact the agency.",
                    "question_to_ask": "Which services are currently available?",
                },
            ],
            "reminder": "The agencies make all decisions.",
        }
        captured: dict = {}

        class FakeInteractions:
            def create(self, **kwargs):
                captured.update(kwargs)
                return types.SimpleNamespace(output_text=json.dumps(generated))

        class FakeClient:
            def __init__(self, api_key):
                captured["api_key"] = api_key
                self.interactions = FakeInteractions()

        fake_genai = types.ModuleType("google.genai")
        fake_genai.Client = FakeClient
        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai

        with mock.patch.dict(
            sys.modules,
            {"google": fake_google, "google.genai": fake_genai},
        ):
            guide = generate_action_guide(MATCHES, api_key="test-key")

        self.assertEqual(guide, generated)
        self.assertFalse(captured["store"])
        self.assertNotIn("https://", captured["input"])
        self.assertNotIn("$27,000", captured["input"])

    def test_gemini_may_reorder_programs_without_changing_membership(self) -> None:
        reordered = {
            "introduction": "Suggested order.",
            "steps": [
                {
                    "program_id": "local-support",
                    "action": "Contact the agency.",
                    "question_to_ask": "What is available?",
                },
                {
                    "program_id": "florida-snap",
                    "action": "Review the program.",
                    "question_to_ask": "What should I verify?",
                },
            ],
            "reminder": "Agencies decide.",
        }

        class FakeInteractions:
            def create(self, **kwargs):
                return types.SimpleNamespace(output_text=json.dumps(reordered))

        class FakeClient:
            def __init__(self, api_key):
                self.interactions = FakeInteractions()

        fake_genai = types.ModuleType("google.genai")
        fake_genai.Client = FakeClient
        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai

        with mock.patch.dict(
            sys.modules,
            {"google": fake_google, "google.genai": fake_genai},
        ):
            guide = generate_action_guide(MATCHES, api_key="test-key")

        self.assertEqual(guide, reordered)

    def test_gemini_generated_link_uses_fallback(self) -> None:
        invalid = build_fallback_guide(MATCHES, "English")
        invalid["steps"][0]["action"] = "Visit https://invented.example now."

        class FakeInteractions:
            def create(self, **kwargs):
                return types.SimpleNamespace(output_text=json.dumps(invalid))

        class FakeClient:
            def __init__(self, api_key):
                self.interactions = FakeInteractions()

        fake_genai = types.ModuleType("google.genai")
        fake_genai.Client = FakeClient
        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai

        with mock.patch.dict(
            sys.modules,
            {"google": fake_google, "google.genai": fake_genai},
        ):
            guide = generate_action_guide(MATCHES, api_key="test-key")

        self.assertEqual(guide, build_fallback_guide(MATCHES, "English"))


if __name__ == "__main__":
    unittest.main()
