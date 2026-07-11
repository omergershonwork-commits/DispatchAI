import json
from typing import Any, Protocol

from pydantic import ValidationError

from app.schemas.incident import INCIDENT_ONLY_REPLY, IncidentExtractionResult, IncidentMissingField
from app.services.qwen_client import QwenClient, QwenClientError, QwenGenerateResponse

ACTIONABLE_REQUIRED_FIELDS: tuple[IncidentMissingField, ...] = (
    "location_text",
    "incident_type",
    "needs",
)

FOLLOW_UP_FIELD_PRIORITY: tuple[IncidentMissingField, ...] = (
    "location_text",
    "incident_type",
    "needs",
    "casualties_text",
    "phone_number",
    "contact_name",
)

FOLLOW_UP_QUESTIONS: dict[IncidentMissingField, str] = {
    "location_text": "Where exactly is help needed?",
    "incident_type": "What happened?",
    "needs": "What help do you need right now?",
    "casualties_text": "Describe how many people are affected and their condition, if known.",
    "phone_number": "What phone number can responders use if Telegram disconnects?",
    "contact_name": "Who should responders ask for when they arrive?",
}

INCIDENT_EXTRACTION_RESPONSE_SCHEMA = """
{
  "is_incident": true,
  "title": "concise 2-4 word title",
  "summary": "clear analysis of the report",
  "incident_type": "medical | rescue | security | fire | earthquake | flood | explosion | building_collapse | evacuation | food | shelter | transport | other | null",
  "location_text": "free-text location or null",
  "urgency": "unknown | low | medium | high | critical",
  "casualties_text": "free-text affected-person description or null",
  "contact_name": "name or null",
  "phone_number": "phone or null",
  "needs": ["specific requested help"],
  "confidence": 0.0,
  "missing_fields": ["location_text"],
  "follow_up_question": "one focused question or null",
  "should_create_incident": false,
  "should_ask_follow_up": true,
  "rejection_reason": "reason if not an incident, otherwise null"
}
""".strip()

INCIDENT_EXTRACTION_INSTRUCTIONS = """
You are a structured incident extraction engine.
Return only valid JSON using the exact schema below. Do not wrap it in Markdown.
Do not invent missing facts. Use null for unknown optional values.

Create title as a concise 2-4 word label suitable for a list. Keep summary as the fuller analysis.
Use casualties_text for a precise free-text description of affected people. Do not reduce it to only a number.

Set confidence from 0.0 to 1.0 for extraction clarity and coherence, not factual verification:
- 0.85-1.00: event, location, and requested help are clear and mutually consistent.
- 0.60-0.84: useful report with one or more uncertain or missing secondary details.
- 0.30-0.59: vague or fragmented report with limited actionable detail.
- 0.00-0.29: mostly unreadable, unrelated, or internally inconsistent.

Treat clear descriptions of safety, medical, rescue, fire, disaster, evacuation, supply, shelter,
or transport needs as incidents even when the sender does not explicitly ask for help.
Infer an obvious need from the described event, but do not invent specific facts.

When conversation context is supplied, merge the latest message with known incident facts.
Preserve known facts unless the latest message clearly corrects them. A short answer may answer the
previous follow-up question and must not automatically be treated as a new report.

If the message is unrelated, set is_incident to false, urgency to unknown, needs to an empty list,
should_create_incident and should_ask_follow_up to false, and explain the rejection.
If important details are missing, ask one focused follow-up question.
""".strip()


class QwenGenerator(Protocol):
    def generate(self, prompt: str) -> QwenGenerateResponse:
        """Generate assistant text for the supplied prompt."""


class IncidentExtractionError(RuntimeError):
    """Raised when extraction output cannot be parsed or validated."""


class IncidentExtractionService:
    def __init__(self, qwen_client: QwenGenerator | None = None) -> None:
        self.qwen_client = qwen_client or QwenClient()

    def extract_from_text(self, message_text: str) -> IncidentExtractionResult:
        if not message_text.strip():
            raise ValueError("Message text must not be empty.")

        prompt = build_incident_extraction_prompt(message_text)
        try:
            model_response = self.qwen_client.generate(prompt)
        except QwenClientError:
            raise
        return parse_incident_extraction_response(model_response.text)


def build_incident_extraction_prompt(message_text: str) -> str:
    return f"""{INCIDENT_EXTRACTION_INSTRUCTIONS}

Return JSON with this exact shape:
{INCIDENT_EXTRACTION_RESPONSE_SCHEMA}

Message or conversation context:
{message_text.strip()}
""".strip()


def parse_incident_extraction_response(response_text: str) -> IncidentExtractionResult:
    json_text = extract_json_object_text(response_text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise IncidentExtractionError("Incident extraction response was not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise IncidentExtractionError("Incident extraction response JSON must be an object.")

    normalized_payload = normalize_extraction_payload(payload)
    try:
        result = IncidentExtractionResult.parse_obj(normalized_payload)
    except ValidationError as exc:
        raise IncidentExtractionError("Incident extraction response did not match the expected schema.") from exc
    return apply_extraction_decision_rules(result)


def normalize_extraction_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize old or imperfect model output into the current contract."""

    normalized = dict(payload)
    normalized["title"] = normalize_title(
        normalized.get("title"),
        normalized.get("summary"),
        normalized.get("incident_type"),
    )

    if not normalized.get("casualties_text") and normalized.get("people_count") is not None:
        normalized["casualties_text"] = f"{normalized['people_count']} affected"

    if normalized.get("confidence") is None:
        normalized["confidence"] = 0.0
    return normalized


def normalize_title(title: Any, summary: Any, incident_type: Any) -> str:
    """Return a stable 2-4 word title without relying solely on model formatting."""

    candidate = str(title or "").strip()
    if not candidate:
        candidate = str(incident_type or "").replace("_", " ").strip()
    if not candidate:
        candidate = str(summary or "Incident report").strip()

    words = candidate.split()
    if len(words) > 4:
        words = words[:4]
    if len(words) == 1:
        words.append("incident")
    normalized = " ".join(words).strip()
    return normalized[:160] or "Incident report"


def apply_extraction_decision_rules(result: IncidentExtractionResult) -> IncidentExtractionResult:
    if not result.is_incident:
        return result.copy(
            update={
                "should_create_incident": False,
                "should_ask_follow_up": False,
                "missing_fields": [],
                "follow_up_question": None,
                "rejection_reason": result.rejection_reason or INCIDENT_ONLY_REPLY,
            }
        )

    missing_fields = compute_missing_fields(result)
    should_create_incident = has_actionable_incident_details(result, missing_fields)
    should_ask_follow_up = bool(missing_fields) and not should_create_incident
    follow_up_question = build_follow_up_question(missing_fields) if should_ask_follow_up else None

    return result.copy(
        update={
            "missing_fields": missing_fields,
            "should_create_incident": should_create_incident,
            "should_ask_follow_up": should_ask_follow_up,
            "follow_up_question": follow_up_question,
            "rejection_reason": None,
        }
    )


def compute_missing_fields(result: IncidentExtractionResult) -> list[IncidentMissingField]:
    missing_fields: list[IncidentMissingField] = []
    if not result.location_text:
        missing_fields.append("location_text")
    if not result.incident_type:
        missing_fields.append("incident_type")
    if not result.needs:
        missing_fields.append("needs")
    if not result.casualties_text:
        missing_fields.append("casualties_text")
    if not result.phone_number:
        missing_fields.append("phone_number")
    if not result.contact_name:
        missing_fields.append("contact_name")
    return [field for field in FOLLOW_UP_FIELD_PRIORITY if field in missing_fields]


def has_actionable_incident_details(
    result: IncidentExtractionResult,
    missing_fields: list[IncidentMissingField],
) -> bool:
    if not result.is_incident:
        return False
    return not any(field in missing_fields for field in ACTIONABLE_REQUIRED_FIELDS)


def build_follow_up_question(missing_fields: list[IncidentMissingField]) -> str | None:
    prioritized = [field for field in FOLLOW_UP_FIELD_PRIORITY if field in missing_fields]
    if not prioritized:
        return None
    return " ".join(FOLLOW_UP_QUESTIONS[field] for field in prioritized[:2])


def extract_json_object_text(response_text: str) -> str:
    stripped_response = response_text.strip()
    if not stripped_response:
        raise IncidentExtractionError("Incident extraction response was empty.")
    if stripped_response.startswith("```"):
        stripped_response = strip_markdown_code_fence(stripped_response)
    if stripped_response.startswith("{") and stripped_response.endswith("}"):
        return stripped_response

    object_start = stripped_response.find("{")
    object_end = stripped_response.rfind("}")
    if object_start == -1 or object_end == -1 or object_end <= object_start:
        raise IncidentExtractionError("Incident extraction response did not contain a JSON object.")
    return stripped_response[object_start : object_end + 1]


def strip_markdown_code_fence(response_text: str) -> str:
    lines = response_text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
