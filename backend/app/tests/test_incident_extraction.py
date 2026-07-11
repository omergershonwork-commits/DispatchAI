import pytest

from app.schemas.incident import INCIDENT_ONLY_REPLY, IncidentExtractionResult
from app.services.incident_extraction import (
    IncidentExtractionError,
    IncidentExtractionService,
    build_follow_up_question,
    build_incident_extraction_prompt,
    compute_missing_fields,
    extract_json_object_text,
    has_actionable_incident_details,
    parse_incident_extraction_response,
)
from app.services.qwen_client import QwenGenerateResponse


class FakeQwenClient:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> QwenGenerateResponse:
        self.last_prompt = prompt
        return QwenGenerateResponse(model="fake-qwen", text=self.response_text, raw_response={})


def valid_incident_json() -> str:
    return """
    {
      "is_incident": true,
      "title": "Medical assistance request",
      "summary": "Person needs medical help near Dizengoff Center.",
      "incident_type": "medical",
      "location_text": "Dizengoff Center",
      "urgency": "high",
      "casualties_text": "One person needs assistance",
      "contact_name": "Omer",
      "phone_number": "0501234567",
      "needs": ["medical help", "fast callback"],
      "confidence": 0.91,
      "missing_fields": [],
      "follow_up_question": null,
      "should_create_incident": true,
      "should_ask_follow_up": false,
      "rejection_reason": null
    }
    """


def legacy_incident_json() -> str:
    return """
    {
      "is_incident": true,
      "summary": "Person needs medical help near Dizengoff Center.",
      "incident_type": "medical",
      "location_text": "Dizengoff Center",
      "urgency": "high",
      "people_count": 1,
      "contact_name": "Omer",
      "phone_number": "0501234567",
      "needs": ["medical help"],
      "confidence": 0.88,
      "missing_fields": [],
      "follow_up_question": null,
      "should_create_incident": true,
      "should_ask_follow_up": false,
      "rejection_reason": null
    }
    """


def partial_incident_json() -> str:
    return """
    {
      "is_incident": true,
      "title": "Urgent assistance request",
      "summary": "Someone needs urgent help.",
      "incident_type": "medical",
      "location_text": null,
      "urgency": "high",
      "casualties_text": null,
      "contact_name": null,
      "phone_number": null,
      "needs": [],
      "confidence": 0.42,
      "missing_fields": [],
      "follow_up_question": null,
      "should_create_incident": true,
      "should_ask_follow_up": false,
      "rejection_reason": null
    }
    """


def unrelated_message_json() -> str:
    return """
    {
      "is_incident": false,
      "title": "Unrelated message",
      "summary": "The sender asked an unrelated question.",
      "incident_type": null,
      "location_text": null,
      "urgency": "unknown",
      "casualties_text": null,
      "contact_name": null,
      "phone_number": null,
      "needs": [],
      "confidence": 0.96,
      "missing_fields": ["location_text"],
      "follow_up_question": "What city are you in?",
      "should_create_incident": true,
      "should_ask_follow_up": true,
      "rejection_reason": null
    }
    """


def test_prompt_contains_dashboard_fields_and_confidence_rubric() -> None:
    prompt = build_incident_extraction_prompt("Need help near Dizengoff Center")

    assert "Return only valid JSON" in prompt
    assert '"title"' in prompt
    assert '"casualties_text"' in prompt
    assert "0.85-1.00" in prompt
    assert "Need help near Dizengoff Center" in prompt


def test_service_returns_validated_dashboard_fields() -> None:
    fake_qwen = FakeQwenClient(valid_incident_json())
    result = IncidentExtractionService(qwen_client=fake_qwen).extract_from_text(
        "Omer needs help near Dizengoff Center"
    )

    assert isinstance(result, IncidentExtractionResult)
    assert result.title == "Medical assistance request"
    assert result.casualties_text == "One person needs assistance"
    assert result.confidence == 0.91
    assert result.should_create_incident is True
    assert result.missing_fields == []


def test_legacy_people_count_is_converted_and_title_is_generated() -> None:
    result = parse_incident_extraction_response(legacy_incident_json())

    assert result.people_count == 1
    assert result.casualties_text == "1 affected"
    assert 2 <= len(result.title.split()) <= 4


def test_title_is_limited_to_four_words() -> None:
    payload = valid_incident_json().replace(
        '"Medical assistance request"',
        '"Very long detailed medical assistance request title"',
    )
    result = parse_incident_extraction_response(payload)
    assert result.title == "Very long detailed medical"


def test_parser_accepts_markdown_fenced_json() -> None:
    result = parse_incident_extraction_response(f"```json\n{valid_incident_json()}\n```")
    assert result.is_incident is True


def test_extract_json_object_text_finds_embedded_json() -> None:
    json_text = extract_json_object_text(f"Result:\n{valid_incident_json()}\nDone")
    assert json_text.startswith("{")
    assert json_text.endswith("}")


def test_parser_rejects_invalid_or_incomplete_json() -> None:
    with pytest.raises(IncidentExtractionError, match="valid JSON"):
        parse_incident_extraction_response("{not valid json}")
    with pytest.raises(IncidentExtractionError, match="expected schema"):
        parse_incident_extraction_response('{"is_incident": true}')


def test_empty_message_is_rejected_before_model_call() -> None:
    service = IncidentExtractionService(qwen_client=FakeQwenClient(valid_incident_json()))
    with pytest.raises(ValueError, match="Message text must not be empty"):
        service.extract_from_text("   ")


def test_non_incident_is_rejected_without_follow_up() -> None:
    result = parse_incident_extraction_response(unrelated_message_json())

    assert result.is_incident is False
    assert result.should_create_incident is False
    assert result.should_ask_follow_up is False
    assert result.missing_fields == []
    assert result.rejection_reason == INCIDENT_ONLY_REPLY


def test_partial_incident_gets_deterministic_follow_up() -> None:
    result = parse_incident_extraction_response(partial_incident_json())

    assert result.should_create_incident is False
    assert result.should_ask_follow_up is True
    assert result.missing_fields[:2] == ["location_text", "needs"]
    assert result.follow_up_question == "Where exactly is help needed? What help do you need right now?"


def test_missing_fields_use_casualty_text_not_numeric_count() -> None:
    result = parse_incident_extraction_response(partial_incident_json())
    assert compute_missing_fields(result) == [
        "location_text",
        "needs",
        "casualties_text",
        "phone_number",
        "contact_name",
    ]
    assert has_actionable_incident_details(result, result.missing_fields) is False


def test_follow_up_question_asks_at_most_two_questions() -> None:
    question = build_follow_up_question(["location_text", "needs", "casualties_text"])
    assert question == "Where exactly is help needed? What help do you need right now?"
