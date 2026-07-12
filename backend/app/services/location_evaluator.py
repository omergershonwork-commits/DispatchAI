import json
import re
from typing import Protocol, List
import httpx
from pydantic import BaseModel, ValidationError

from app.services.qwen_client import QwenGenerateResponse, QwenClientError

class ArcGISCandidate(BaseModel):
    address: str
    location: dict[str, float]
    score: float

class ArcGISClient:
    """Client for the free ArcGIS Geocoding API."""
    def __init__(self):
        self.base_url = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"

    def clean_query(self, query: str) -> str:
        """Strip conversational filler that confuses geocoders."""
        clean = re.sub(r"(?i)\b(near the|in the|next to|at the|inside the|outside the|around the|close to|by the|near|in|at|by)\b", " ", query)
        clean = re.sub(r"(?i)\b(United Stated|United States|Israel)\b", "", clean)
        clean = re.sub(r"^,\s*", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def search(self, query: str) -> List[ArcGISCandidate]:
        cleaned_query = self.clean_query(query)
        if not cleaned_query:
            return []
        
        params = {
            "f": "json",
            "singleLine": cleaned_query,
            "maxLocations": 3
        }
        try:
            with httpx.Client() as client:
                response = client.get(self.base_url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates", [])
                return [ArcGISCandidate(**c) for c in candidates]
        except Exception:
            return []


class QwenGenerator(Protocol):
    def generate(self, prompt: str) -> QwenGenerateResponse:
        ...


class LocationEvaluationResult(BaseModel):
    reasoning: str
    is_confident: bool
    best_candidate_index: int | None
    follow_up_question: str | None


LOCATION_EVALUATION_INSTRUCTIONS = """
You are an expert location evaluator and dispatcher.
Your goal is to evaluate if any of the provided geocoder results accurately matches the user's reported location.

INPUT:
1. User's Raw Text: The original message sent by the user.
2. Extracted Location: The location phrase extracted from the text.
3. Geocoder Results: A list of candidate locations returned by the mapping API.

TASK:
- Analyze the user's raw text to understand the intended location context.
- Evaluate each Geocoder Result against the intended location.
- If one of the results is highly likely to be the correct location, set "is_confident" to true and provide its "best_candidate_index" (0-indexed).
- If the results are ambiguous, too generic, or none of them match, set "is_confident" to false, "best_candidate_index" to null, and generate a clear "follow_up_question" asking the user to clarify the location.

CRITICAL RULE:
- Your response MUST be valid JSON matching the schema below. Do NOT wrap in Markdown.

{
  "reasoning": "Explain step-by-step why a candidate matches or why clarification is needed.",
  "is_confident": true,
  "best_candidate_index": 0,
  "follow_up_question": null
}
""".strip()


class LocationEvaluatorService:
    def __init__(self, qwen_client: QwenGenerator, geocoder: ArcGISClient | None = None):
        self.qwen_client = qwen_client
        self.geocoder = geocoder or ArcGISClient()

    def evaluate_location(self, raw_text: str, location_text: str) -> dict:
        candidates = self.geocoder.search(location_text)
        if not candidates:
            return {
                "latitude": None,
                "longitude": None,
                "needs_follow_up": True,
                "follow_up_question": "I couldn't find that location. Could you provide a more specific address or nearby landmark?"
            }
        
        candidates_str = "\n".join([f"[{i}] {c.address} (Score: {c.score})" for i, c in enumerate(candidates)])
        
        prompt = f"{LOCATION_EVALUATION_INSTRUCTIONS}\n\nUser's Raw Text: {raw_text}\nExtracted Location: {location_text}\nGeocoder Results:\n{candidates_str}"
        
        try:
            response = self.qwen_client.generate(prompt)
            raw_content = response.content.strip()
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            
            data = json.loads(raw_content)
            result = LocationEvaluationResult(**data)
            
            if result.is_confident and result.best_candidate_index is not None and 0 <= result.best_candidate_index < len(candidates):
                best_match = candidates[result.best_candidate_index]
                return {
                    "latitude": best_match.location.get("y"),
                    "longitude": best_match.location.get("x"),
                    "needs_follow_up": False,
                    "follow_up_question": None
                }
            else:
                return {
                    "latitude": None,
                    "longitude": None,
                    "needs_follow_up": True,
                    "follow_up_question": result.follow_up_question or "Could you clarify the exact location?"
                }
        except (json.JSONDecodeError, ValidationError, QwenClientError):
            # Fallback to the first result if the evaluator fails but there is a high scoring match
            if candidates[0].score >= 95:
                return {
                    "latitude": candidates[0].location.get("y"),
                    "longitude": candidates[0].location.get("x"),
                    "needs_follow_up": False,
                    "follow_up_question": None
                }
            return {
                "latitude": None,
                "longitude": None,
                "needs_follow_up": True,
                "follow_up_question": "Could you clarify the exact location?"
            }
