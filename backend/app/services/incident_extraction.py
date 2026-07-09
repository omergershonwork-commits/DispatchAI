import json
from typing import Protocol

from pydantic import ValidationError

from app.schemas.incident import IncidentExtractionResult
from app.services.qwen_client import QwenClient, QwenClientError, QwenGenerateResponse

INCIDENT_EXTRACTION_RESPONSE_SCHEMA = """
{
  "is_incident": true,
  "summary": "short summary of what happened",
  "incident_type": "medical | rescue | food | shelter | transport | other | null",
  "location_text": "free-text location or null",
  "urgency": "unknown | low | medium | high | critical",
  "people_count": 1,
  "contact_name": "name or null",
  "phone_number": "phone or null",
  "needs": ["specific requested help"],
  "confidence": 0.0
}
""".strip()
"""JSON shape the model must return for incident extraction."""

INCIDENT_EXTRACTION_INSTRUCTIONS = """
You are an emergency-dispatch incident extraction engine.
Extract structured incident details from one Telegram message.
Return only valid JSON. Do not wrap the JSON in Markdown.
Do not invent missing facts. Use null for unknown optional values.
Use confidence between 0.0 and 1.0.
If the message is not asking for help or reporting an incident, set is_incident to false,
use urgency "unknown", keep needs empty, and summarize why it is not an incident.
""".strip()
"""Prompt instructions sent before the Telegram message text."""


class QwenGenerator(Protocol):
    """Protocol for objects that can generate text from a prompt."""

    def generate(self, prompt: str) -> QwenGenerateResponse:
        """Generate assistant text for the supplied prompt."""


class IncidentExtractionError(RuntimeError):
    """Raised when incident extraction cannot parse or validate model output."""


class IncidentExtractionService:
    """Service that extracts structured incident details using Qwen."""

    def __init__(self, qwen_client: QwenGenerator | None = None) -> None:
        """Create an extraction service with an injectable Qwen-compatible client."""

        self.qwen_client = qwen_client or QwenClient()
        """Client used to generate model responses for extraction prompts."""

    def extract_from_text(self, message_text: str) -> IncidentExtractionResult:
        """Extract validated incident details from a Telegram message text."""

        if not message_text.strip():
            raise ValueError("Message text must not be empty.")

        prompt = build_incident_extraction_prompt(message_text)
        try:
            model_response = self.qwen_client.generate(prompt)
        except QwenClientError:
            raise

        return parse_incident_extraction_response(model_response.text)


def build_incident_extraction_prompt(message_text: str) -> str:
    """Build the Qwen prompt for extracting incident details from text."""

    return f"""{INCIDENT_EXTRACTION_INSTRUCTIONS}

Return JSON with this exact shape:
{INCIDENT_EXTRACTION_RESPONSE_SCHEMA}

Telegram message:
{message_text.strip()}
""".strip()


def parse_incident_extraction_response(response_text: str) -> IncidentExtractionResult:
    """Parse and validate the JSON returned by the incident extraction prompt."""

    json_text = extract_json_object_text(response_text)

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise IncidentExtractionError("Incident extraction response was not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise IncidentExtractionError("Incident extraction response JSON must be an object.")

    try:
        return IncidentExtractionResult.parse_obj(payload)
    except ValidationError as exc:
        raise IncidentExtractionError("Incident extraction response did not match the expected schema.") from exc


def extract_json_object_text(response_text: str) -> str:
    """Return the JSON object text from a raw model response."""

    stripped_response = response_text.strip()
    """Model response stripped of leading and trailing whitespace."""

    if not stripped_response:
        raise IncidentExtractionError("Incident extraction response was empty.")

    if stripped_response.startswith("```"):
        stripped_response = strip_markdown_code_fence(stripped_response)

    if stripped_response.startswith("{") and stripped_response.endswith("}"):
        return stripped_response

    object_start = stripped_response.find("{")
    """Index of the first JSON object opening brace in the model response."""

    object_end = stripped_response.rfind("}")
    """Index of the last JSON object closing brace in the model response."""

    if object_start == -1 or object_end == -1 or object_end <= object_start:
        raise IncidentExtractionError("Incident extraction response did not contain a JSON object.")

    return stripped_response[object_start : object_end + 1]


def strip_markdown_code_fence(response_text: str) -> str:
    """Remove a surrounding Markdown code fence from model output."""

    lines = response_text.splitlines()
    """Model response split into lines so fence markers can be removed safely."""

    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]

    return "\n".join(lines).strip()
