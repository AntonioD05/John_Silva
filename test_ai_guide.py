"""Tests for Gemini guide constraints and deterministic fallbacks."""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest import mock

import ai_guide
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


def fake_google_modules(
    *, output_text: str | None = None, error: Exception | None = None
) -> tuple[types.ModuleType, types.ModuleType, dict]:
    captured: dict = {"request_count": 0, "client_closed": False}

    class FakeHttpRetryOptions:
        def __init__(self, *, attempts):
            self.attempts = attempts

    class FakeHttpOptions:
        def __init__(self, *, timeout, retry_options):
            self.timeout = timeout
            self.retry_options = retry_options

    class FakeInteractions:
        def create(self, **kwargs):
            captured["request_count"] += 1
            captured.update(kwargs)
            if error is not None:
                raise error
            return types.SimpleNamespace(output_text=output_text)

    class FakeClient:
        def __init__(self, *, api_key, http_options):
            captured["api_key"] = api_key
            captured["http_options"] = http_options
            self.interactions = FakeInteractions()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            captured["client_closed"] = True

    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_genai.types = types.SimpleNamespace(
        HttpOptions=FakeHttpOptions,
        HttpRetryOptions=FakeHttpRetryOptions,
    )
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai
    return fake_google, fake_genai, captured


class ActionGuideTests(unittest.TestCase):
    def setUp(self) -> None:
        ai_guide._GUIDE_CACHE.clear()

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
        fake_google, fake_genai, captured = fake_google_modules(
            output_text=json.dumps(generated)
        )

        with mock.patch.dict(
            sys.modules,
            {"google": fake_google, "google.genai": fake_genai},
        ):
            guide = generate_action_guide(MATCHES, api_key="test-key")

        self.assertEqual(guide, generated)
        self.assertFalse(captured["store"])
        self.assertEqual(captured["http_options"].timeout, 15_000)
        self.assertEqual(captured["http_options"].retry_options.attempts, 1)
        self.assertTrue(captured["client_closed"])
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

        fake_google, fake_genai, _ = fake_google_modules(
            output_text=json.dumps(reordered)
        )

        with mock.patch.dict(
            sys.modules,
            {"google": fake_google, "google.genai": fake_genai},
        ):
            guide = generate_action_guide(MATCHES, api_key="test-key")

        self.assertEqual(guide, reordered)

    def test_gemini_generated_link_uses_fallback(self) -> None:
        invalid = build_fallback_guide(MATCHES, "English")
        invalid["steps"][0]["action"] = "Visit https://invented.example now."

        fake_google, fake_genai, _ = fake_google_modules(
            output_text=json.dumps(invalid)
        )

        with mock.patch.dict(
            sys.modules,
            {"google": fake_google, "google.genai": fake_genai},
        ):
            guide = generate_action_guide(MATCHES, api_key="test-key")

        self.assertEqual(guide, build_fallback_guide(MATCHES, "English"))

    def test_429_503_and_timeout_exceptions_return_fallback(self) -> None:
        exception_cases = (
            ("429", type("TooManyRequests", (Exception,), {})("quota exceeded"), 429),
            ("503", type("ServiceUnavailable", (Exception,), {})("unavailable"), 503),
            ("timeout", TimeoutError("request timed out"), None),
        )

        for label, error, status_code in exception_cases:
            with self.subTest(label=label):
                ai_guide._GUIDE_CACHE.clear()
                if status_code is not None:
                    error.status_code = status_code
                    error.message = str(error)
                fake_google, fake_genai, captured = fake_google_modules(error=error)

                with mock.patch.dict(
                    sys.modules,
                    {"google": fake_google, "google.genai": fake_genai},
                ), self.assertLogs("ai_guide", level="WARNING") as logs:
                    guide = generate_action_guide(MATCHES, api_key="secret-test-key")

                self.assertEqual(
                    guide, build_fallback_guide(MATCHES, "English")
                )
                self.assertEqual(captured["request_count"], 1)
                self.assertTrue(captured["client_closed"])
                log_output = " ".join(logs.output)
                self.assertIn(type(error).__name__, log_output)
                self.assertIn(str(status_code or "unknown"), log_output)
                self.assertNotIn("secret-test-key", log_output)
                self.assertNotIn("$27,000", log_output)
                self.assertNotIn("https://", log_output)

    def test_successful_guides_are_cached_by_safe_program_data(self) -> None:
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
        fake_google, fake_genai, captured = fake_google_modules(
            output_text=json.dumps(generated)
        )
        second_matches = [dict(match) for match in MATCHES]
        second_matches[0]["matched_reasons"] = ["Different private detail"]
        second_matches[0]["source_url"] = "https://different.example"

        with mock.patch.dict(
            sys.modules,
            {"google": fake_google, "google.genai": fake_genai},
        ):
            first = generate_action_guide(MATCHES, api_key="test-key")
            second = generate_action_guide(second_matches, api_key="test-key")

        self.assertEqual(first, generated)
        self.assertEqual(second, generated)
        self.assertEqual(captured["request_count"], 1)


if __name__ == "__main__":
    unittest.main()
