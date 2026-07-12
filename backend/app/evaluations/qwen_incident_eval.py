from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from app.schemas.incident import IncidentExtractionResult

DEFAULT_CASES_PATH = Path(__file__).with_name("live_qwen_cases.json")


@dataclass(frozen=True)
class EvaluationOutcome:
    name: str
    passed: bool
    checks: dict[str, bool]
    failed_checks: list[str]
    result: dict[str, Any] | None = None
    error: str | None = None
    duration_seconds: float | None = None


def load_evaluation_cases(path: str | Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    case_path = Path(path)
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Live Qwen evaluation dataset must contain a non-empty JSON list.")

    names: set[str] = set()
    cases: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Each live Qwen evaluation case must be a JSON object.")
        name = str(item.get("name") or "").strip()
        message = str(item.get("message") or "").strip()
        if not name or not message:
            raise ValueError("Each live Qwen evaluation case requires name and message.")
        if name in names:
            raise ValueError(f"Duplicate live Qwen evaluation case name: {name}")
        names.add(name)
        cases.append(dict(item))
    return cases


def evaluate_extraction(
    case: dict[str, Any],
    result: IncidentExtractionResult,
    *,
    duration_seconds: float | None = None,
) -> EvaluationOutcome:
    checks: dict[str, bool] = {}
    expected_incident = bool(case["is_incident"])

    checks["is_incident"] = result.is_incident is expected_incident
    checks["summary_nonempty"] = bool(result.summary.strip())
    checks["confidence_range"] = _number_in_range(
        result.confidence,
        float(case.get("confidence_min", 0.0)),
        float(case.get("confidence_max", 1.0)),
    )

    expected_urgencies = _normalized_values(case.get("urgencies", []))
    if expected_urgencies:
        checks["urgency"] = normalize_text(result.urgency) in expected_urgencies

    if "should_create" in case:
        checks["should_create"] = result.should_create_incident is bool(case["should_create"])
    if "should_ask_follow_up" in case:
        checks["should_ask_follow_up"] = result.should_ask_follow_up is bool(
            case["should_ask_follow_up"]
        )

    if expected_incident:
        title_word_count = len([word for word in result.title.split() if word.strip()])
        checks["title_2_to_4_words"] = 2 <= title_word_count <= 4

        expected_types = _normalized_values(case.get("incident_types", []))
        if expected_types:
            checks["incident_type"] = normalize_text(result.incident_type or "") in expected_types

        location_terms = case.get("location_any", [])
        if location_terms:
            checks["location"] = contains_any(result.location_text or "", location_terms)

        if case.get("location_must_be_missing"):
            checks["location_missing"] = not bool((result.location_text or "").strip())
            checks["location_in_missing_fields"] = "location_text" in result.missing_fields

        need_groups = case.get("need_groups", [])
        if need_groups:
            needs_text = " ".join(result.needs)
            for index, group in enumerate(need_groups, start=1):
                checks[f"needs_group_{index}"] = contains_any(needs_text, group)

        casualty_terms = case.get("casualties_any", [])
        if casualty_terms:
            checks["casualties_text"] = contains_any(result.casualties_text or "", casualty_terms)
    else:
        checks["rejection_reason"] = bool((result.rejection_reason or "").strip())
        checks["empty_needs"] = result.needs == []
        checks["no_follow_up"] = not result.should_ask_follow_up
        checks["not_created"] = not result.should_create_incident

    failed_checks = [name for name, passed in checks.items() if not passed]
    return EvaluationOutcome(
        name=str(case["name"]),
        passed=not failed_checks,
        checks=checks,
        failed_checks=failed_checks,
        result=result.dict(),
        duration_seconds=duration_seconds,
    )


def failed_evaluation(
    case: dict[str, Any],
    error: Exception | str,
    *,
    duration_seconds: float | None = None,
) -> EvaluationOutcome:
    return EvaluationOutcome(
        name=str(case["name"]),
        passed=False,
        checks={"request_and_schema": False},
        failed_checks=["request_and_schema"],
        error=str(error),
        duration_seconds=duration_seconds,
    )


def success_rate(outcomes: list[EvaluationOutcome]) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for outcome in outcomes if outcome.passed) / len(outcomes)


def passes_success_rate(
    outcomes: list[EvaluationOutcome],
    threshold: float,
) -> bool:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("Success-rate threshold must be between 0 and 1.")
    return success_rate(outcomes) > threshold


def check_accuracy(outcomes: list[EvaluationOutcome]) -> float:
    total = sum(len(outcome.checks) for outcome in outcomes)
    if total == 0:
        return 0.0
    passed = sum(
        1
        for outcome in outcomes
        for check_passed in outcome.checks.values()
        if check_passed
    )
    return passed / total


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def contains_any(value: str, terms: list[str]) -> bool:
    normalized_value = normalize_text(value)
    return any(normalize_text(term) in normalized_value for term in terms if str(term).strip())


def _normalized_values(values: list[str]) -> set[str]:
    return {normalize_text(value) for value in values if str(value).strip()}


def _number_in_range(value: float, minimum: float, maximum: float) -> bool:
    return minimum <= float(value) <= maximum
