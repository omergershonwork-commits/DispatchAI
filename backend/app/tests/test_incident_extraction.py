import pytest

from app.schemas.incident import IncidentExtractionResult
from app.services.incident_extraction import (
    IncidentExtractionError,
    IncidentExtractionService,
    build_incident_extraction_prompt,
    extract_json_object_text,
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
      "confidence": 0.91
    }
    """


def test_build_incident_extraction_prompt_contains_required_sections() -> None:
    """Verify the prompt includes instructions, schema, and source text."""

    prompt = build_incident_extraction_prompt("Need medical help near Dizengoff Center")

    assert "Return only valid JSON" in prompt
    assert "is_incident" in prompt
    assert "location_text" in prompt
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
