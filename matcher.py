"""Deterministic, explainable program matching for the resource navigator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SUPPORTED_OPERATORS = {"lte_by_household_size"}
REQUIRED_PROGRAM_FIELDS = {
    "id",
    "name",
    "category",
    "description",
    "service_area",
    "rules",
    "verification_notes",
    "source_name",
    "source_url",
    "last_checked",
}


def load_programs(path: str = "programs.json") -> list[dict[str, Any]]:
    """Load program records and reject malformed matcher data."""
    with Path(path).open(encoding="utf-8") as program_file:
        programs = json.load(program_file)

    if not isinstance(programs, list):
        raise ValueError("Program data must be a JSON array.")

    seen_ids: set[str] = set()
    for index, program in enumerate(programs):
        if not isinstance(program, dict):
            raise ValueError(f"Program at index {index} must be an object.")

        missing_fields = REQUIRED_PROGRAM_FIELDS - program.keys()
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"Program at index {index} is missing: {missing}.")

        program_id = program["id"]
        if not isinstance(program_id, str) or not program_id:
            raise ValueError(f"Program at index {index} has an invalid id.")
        if program_id in seen_ids:
            raise ValueError(f"Duplicate program id: {program_id}.")
        seen_ids.add(program_id)

        if not isinstance(program["rules"], list):
            raise ValueError(f"Rules for {program_id} must be an array.")
        for rule in program["rules"]:
            if not isinstance(rule, dict):
                raise ValueError(f"Each rule for {program_id} must be an object.")
            if rule.get("operator") not in SUPPORTED_OPERATORS:
                raise ValueError(
                    f"Unsupported operator for {program_id}: {rule.get('operator')}."
                )

    return programs


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _matches_service_area(
    profile: dict[str, Any], service_area: dict[str, Any]
) -> tuple[bool, str | None]:
    """Prescreen geography using only the ZIP code supplied by app.py."""
    zip_code = str(profile.get("zip_code", "")).strip()
    if len(zip_code) != 5 or not zip_code.isdigit():
        return False, None

    if service_area.get("type") != "zip_prefix_range":
        return False, None

    prefix = int(zip_code[:3])
    minimum = service_area.get("min_prefix")
    maximum = service_area.get("max_prefix")
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        return False, None

    if minimum <= prefix <= maximum:
        return True, str(service_area.get("reason", "Your ZIP code matches the service area."))
    return False, None


def _household_income_limit(rule: dict[str, Any], household_size: int) -> float | None:
    values = rule.get("values")
    if not isinstance(values, dict) or household_size < 1:
        return None

    configured_sizes: list[int] = []
    for raw_size in values:
        try:
            configured_sizes.append(int(raw_size))
        except (TypeError, ValueError):
            return None
    if not configured_sizes:
        return None

    if str(household_size) in values:
        limit = values[str(household_size)]
        return float(limit) if _is_number(limit) else None

    largest_size = max(configured_sizes)
    if household_size <= largest_size:
        return None

    base_limit = values.get(str(largest_size))
    additional_amount = rule.get("additional_person_amount")
    if not _is_number(base_limit) or not _is_number(additional_amount):
        return None
    return float(base_limit) + (household_size - largest_size) * float(additional_amount)


def _evaluate_income_rule(
    profile: dict[str, Any], rule: dict[str, Any]
) -> tuple[bool | None, str | None]:
    income = profile.get(rule.get("field"))
    household_size = profile.get(rule.get("household_size_field"))
    if not _is_number(income) or not isinstance(household_size, int):
        return None, None
    if isinstance(household_size, bool) or income < 0 or household_size < 1:
        return None, None

    limit = _household_income_limit(rule, household_size)
    if limit is None:
        return None, None
    if float(income) > limit:
        return False, None

    reason_template = str(
        rule.get(
            "reason",
            "Your reported income is within the configured general prescreen amount.",
        )
    )
    return True, reason_template.format(
        annual_income=income,
        household_size=household_size,
        income_limit=limit,
    )


def find_matches(
    user_profile: dict[str, Any], programs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return explainable resources to investigate, never eligibility decisions."""
    if not isinstance(user_profile, dict) or not isinstance(programs, list):
        return []

    matches: list[dict[str, Any]] = []
    for program in programs:
        if not isinstance(program, dict):
            continue

        service_area = program.get("service_area")
        if not isinstance(service_area, dict):
            continue
        geographic_match, geographic_reason = _matches_service_area(
            user_profile, service_area
        )
        if not geographic_match or geographic_reason is None:
            continue

        matched_reasons = [geographic_reason]
        unmet_reasons: list[str] = []
        should_show = True

        rules = program.get("rules", [])
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                should_show = False
                break

            if rule.get("operator") == "lte_by_household_size":
                outcome, reason = _evaluate_income_rule(user_profile, rule)
            else:
                outcome, reason = None, None

            if outcome is True and reason:
                matched_reasons.append(reason)
            elif outcome is False:
                unmet_reasons.append(str(rule.get("unmet_reason", "A prescreen rule did not match.")))
                if rule.get("required", False):
                    should_show = False
                    break
            elif rule.get("required", False):
                # Missing or unusable data cannot be treated as evidence of eligibility.
                should_show = False
                break

        if not should_show:
            continue

        result = {
            "program_id": program["id"],
            "name": program["name"],
            "category": program["category"],
            "description": program["description"],
            "status": "possible_match",
            "score": len(matched_reasons),
            "matched_reasons": matched_reasons,
            "unmet_reasons": unmet_reasons,
            "needs_verification": list(program.get("verification_notes", [])),
            "source_name": program["source_name"],
            "source_url": program["source_url"],
            "last_checked": program["last_checked"],
        }
        if program.get("apply_url"):
            result["apply_url"] = program["apply_url"]
        matches.append(result)

    return sorted(matches, key=lambda match: (-match["score"], match["name"]))
