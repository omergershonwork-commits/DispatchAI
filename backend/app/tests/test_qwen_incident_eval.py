from app.evaluations.qwen_incident_eval import (
    EvaluationOutcome,
    evaluate_extraction,
    passes_success_rate,
    success_rate,
)
from app.schemas.incident import IncidentExtractionResult


def extraction(**overrides) -> IncidentExtractionResult:
    payload = {
        "is_incident": True,
        "title": "Building Fire",
        "summary": "A building is burning in Nahariya and one resident is trapped.",
        "incident_type": "fire",
        "location_text": "Nahariya near Arena Mall",
        "urgency": "critical",
        "casualties_text": "One resident is trapped",
        "needs": ["firefighters", "rescue"],
        "confidence": 0.95,
        "missing_fields": ["phone_number", "contact_name"],
        "follow_up_question": None,
        "should_create_incident": True,
        "should_ask_follow_up": False,
        "rejection_reason": None,
    }
    payload.update(overrides)
    return IncidentExtractionResult(**payload)


def test_complete_case_passes_all_applicable_checks() -> None:
    case = {
        "name": "fire",
        "message": "fire",
        "is_incident": True,
        "incident_types": ["fire"],
        "urgencies": ["critical"],
        "location_any": ["nahariya"],
        "need_groups": [["fire"], ["rescue"]],
        "casualties_any": ["one", "trapped"],
        "confidence_min": 0.8,
        "should_create": True,
    }

    outcome = evaluate_extraction(case, extraction())

    assert outcome.passed is True
    assert outcome.failed_checks == []
    assert all(outcome.checks.values())


def test_case_fails_when_required_need_is_missing() -> None:
    case = {
        "name": "fire",
        "message": "fire",
        "is_incident": True,
        "incident_types": ["fire"],
        "urgencies": ["critical"],
        "need_groups": [["fire"], ["rescue"]],
        "confidence_min": 0.8,
        "should_create": True,
    }

    outcome = evaluate_extraction(case, extraction(needs=["firefighters"]))

    assert outcome.passed is False
    assert "needs_group_2" in outcome.failed_checks


def test_success_rate_gate_is_strictly_greater_than_ninety_percent() -> None:
    passing = EvaluationOutcome("pass", True, {"x": True}, [])
    failing = EvaluationOutcome("fail", False, {"x": False}, ["x"])

    exactly_ninety = [passing] * 9 + [failing]
    ninety_five = [passing] * 19 + [failing]

    assert success_rate(exactly_ninety) == 0.9
    assert passes_success_rate(exactly_ninety, 0.9) is False
    assert passes_success_rate(ninety_five, 0.9) is True
