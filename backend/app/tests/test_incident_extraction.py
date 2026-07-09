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
    """Test double that returns predetermined Qwen generation text."""

    def __init__(self, response_text: str) -> None:
        """Create a fake client that records prompts and returns fixed text."""

        self.response_text = response_text
        """Assistant text returned from the fake generate call."""

        self.last_prompt: str | None = None
        """Most recent prompt passed to the fake generate call."""

    def generate(self, prompt: str) -> QwenGenerateResponse:
        """Record the prompt and return the configured fake response."""

        self.last_prompt = prompt
        return QwenGenerateResponse(
            model="fake-qwen",
            text=self.response_text,
            raw_response={},
        )


def valid_incident_json() -> str:
    """Return a valid incident extraction JSON response as text."""

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
      "needs": ["medical help", "fast callback"],
      "confidence": 0.91,
      "missing_fields": [],
      "follow_up_question": null,
      "should_create_incident": true,
      "should_ask_follow_up": false,
      "rejection_reason": null
    }
    """


def partial_incident_json() -> str:
    """Return incident JSON with missing details that require follow-up."""

    return """
    {
      "is_incident": true,
      "summary": "Someone needs urgent help.",
      "incident_type": "medical",
      "location_text": null,
      "urgency": "high",
      "people_count": null,
      "contact_name": null,
      "phone_number": null,
      "needs": [],
      "confidence": 0.82,
      "missing_fields": [],
      "follow_up_question": null,
      "should_create_incident": true,
      "should_ask_follow_up": false,
      "rejection_reason": null
    }
    """


def unrelated_message_json() -> str:
    """Return extraction JSON for a non-incident user message."""

    return """
    {
      "is_incident": false,
      "summary": "The sender asked an unrelated general-knowledge question.",
      "incident_type": null,
      "location_text": null,
      "urgency": "unknown",
      "people_count": null,
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


def test_build_incident_extraction_prompt_contains_required_sections() -> None:
    """Verify the prompt includes instructions, schema, and source text."""

    prompt = build_incident_extraction_prompt("Need medical help near Dizengoff Center")

    assert "Return only valid JSON" in prompt
    assert "Do not answer unrelated questions" in prompt
    assert "is_incident" in prompt
    assert "location_text" in prompt
    assert "follow_up_question" in prompt
    assert "Need medical help near Dizengoff Center" in prompt


def test_incident_extraction_service_returns_validated_result() -> None:
    """Verify the service uses Qwen output to return a validated extraction result."""

    fake_qwen = FakeQwenClient(valid_incident_json())
    service = IncidentExtractionService(qwen_client=fake_qwen)

    result = service.extract_from_text("Omer needs medical help near Dizengoff Center. 0501234567")

    assert isinstance(result, IncidentExtractionResult)
    assert result.is_incident is True
    assert result.incident_type == "medical"
    assert result.location_text == "Dizengoff Center"
    assert result.urgency == "high"
    assert result.people_count == 1
    assert result.needs == ["medical help", "fast callback"]
    assert result.should_create_incident is True
    assert result.should_ask_follow_up is False
    assert result.missing_fields == []
    assert result.follow_up_question is None
    assert fake_qwen.last_prompt is not None
    assert "Omer needs medical help" in fake_qwen.last_prompt


def test_parse_incident_extraction_response_accepts_markdown_fenced_json() -> None:
    """Verify parser tolerates fenced JSON even though prompt forbids Markdown."""

    result = parse_incident_extraction_response(f"```json\n{valid_incident_json()}\n```")

    assert result.is_incident is True
    assert result.confidence == 0.91


def test_extract_json_object_text_finds_json_inside_extra_text() -> None:
    """Verify parser can isolate JSON when the model adds surrounding text."""

    json_text = extract_json_object_text(f"Here is the result:\n{valid_incident_json()}\nDone")

    assert json_text.startswith("{")
    assert json_text.endswith("}")


def test_parse_incident_extraction_response_rejects_invalid_json() -> None:
    """Verify invalid JSON raises the domain extraction error."""

    with pytest.raises(IncidentExtractionError, match="valid JSON"):
        parse_incident_extraction_response("{not valid json}")


def test_parse_incident_extraction_response_rejects_missing_required_fields() -> None:
    """Verify schema validation catches incomplete model responses."""

    with pytest.raises(IncidentExtractionError, match="expected schema"):
        parse_incident_extraction_response('{"is_incident": true}')


def test_incident_extraction_service_rejects_empty_message_text() -> None:
    """Verify empty Telegram message text is rejected before calling Qwen."""

    service = IncidentExtractionService(qwen_client=FakeQwenClient(valid_incident_json()))

    with pytest.raises(ValueError, match="Message text must not be empty"):
        service.extract_from_text("   ")


def test_non_incident_message_is_rejected_without_follow_up() -> None:
    """Verify unrelated messages cannot use the extraction layer as a chatbot."""

    result = parse_incident_extraction_response(unrelated_message_json())

    assert result.is_incident is False
    assert result.should_create_incident is False
    assert result.should_ask_follow_up is False
    assert result.missing_fields == []
    assert result.follow_up_question is None
    assert result.rejection_reason == INCIDENT_ONLY_REPLY


def test_partial_incident_gets_follow_up_decision() -> None:
    """Verify missing critical details produce a focused follow-up question."""

    result = parse_incident_extraction_response(partial_incident_json())

    assert result.is_incident is True
    assert result.should_create_incident is False
    assert result.should_ask_follow_up is True
    assert result.missing_fields[:2] == ["location_text", "needs"]
    assert result.follow_up_question == "Where exactly is help needed? What help do you need right now?"
    assert result.rejection_reason is None


def test_compute_missing_fields_orders_fields_by_priority() -> None:
    """Verify backend decision logic prioritizes operationally important missing fields."""

    result = parse_incident_extraction_response(partial_incident_json())

    assert compute_missing_fields(result) == [
        "location_text",
        "needs",
        "people_count",
        "phone_number",
        "contact_name",
    ]


def test_has_actionable_incident_details_requires_core_fields() -> None:
    """Verify incident creation is blocked until core actionable fields exist."""

    result = parse_incident_extraction_response(partial_incident_json())

    assert has_actionable_incident_details(result, result.missing_fields) is False


def test_build_follow_up_question_asks_at_most_two_questions() -> None:
    """Verify follow-up questions stay short for stressed senders."""

    question = build_follow_up_question(["location_text", "needs", "people_count"])

    assert question == "Where exactly is help needed? What help do you need right now?"
