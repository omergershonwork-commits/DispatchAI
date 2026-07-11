import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.dispatch_recommendation import (
    RECOMMENDATION_STATUS_RECOMMENDED,
    DispatchRecommendation,
)
from app.models.incident import INCIDENT_STATUS_READY_FOR_DISPATCH, Incident
from app.models.volunteer import VOLUNTEER_STATUS_AVAILABLE, Volunteer

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "dispatch_scenarios.json"
"""Default dispatch scenario configuration path."""

TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
"""Simple tokenizer for incident and volunteer matching terms."""

SUPPORTED_SCORE_DIMENSIONS = {
    "location",
    "skill_match",
    "response_time",
    "reliability",
    "inventory_match",
    "vehicle_match",
}


class DispatchMatchingError(RuntimeError):
    """Raised when volunteer matching cannot be completed."""


@dataclass(frozen=True)
class DispatchScenario:
    """Scenario configuration used for deterministic volunteer scoring."""

    name: str
    description: str
    keywords: list[str]
    urgencies: list[str]
    weights: dict[str, float]
    preferred_skills: list[str]
    preferred_inventory: list[str]
    preferred_vehicles: list[str]
    urgency_weight_multipliers: dict[str, dict[str, float]]


@dataclass(frozen=True)
class ScenarioSelection:
    """Selected scenario and confidence for an incident."""

    scenario: DispatchScenario
    confidence: float
    matched_terms: list[str]


@dataclass(frozen=True)
class VolunteerScore:
    """Computed score for one volunteer candidate."""

    volunteer_id: int
    total_score: float
    breakdown: dict[str, float]


@dataclass(frozen=True)
class DispatchRecommendationResult:
    """Persisted top volunteer recommendation result."""

    recommendation_id: int
    incident_id: int
    volunteer_id: int
    scenario: str
    rank: int
    total_score: float
    score_breakdown: dict[str, float]


@dataclass(frozen=True)
class DispatchRecommendationBatch:
    """Output returned after generating recommendations for one incident."""

    incident_id: int
    scenario: str
    scenario_confidence: float
    recommendations: list[DispatchRecommendationResult]


class DispatchScenarioConfig:
    """Load and validate dispatch scenario configuration."""

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        self.config_path = config_path

    def load(self) -> tuple[str, float, dict[str, DispatchScenario]]:
        """Return default scenario, confidence threshold, and scenario map."""

        raw_config = json.loads(self.config_path.read_text(encoding="utf-8"))
        default_scenario = raw_config["default_scenario"]
        fallback_threshold = float(raw_config.get("fallback_confidence_threshold", 0.7))
        urgency_multipliers = self._validate_urgency_multipliers(
            raw_config.get("urgency_weight_multipliers", {})
        )

        scenarios = {
            scenario["name"]: DispatchScenario(
                name=scenario["name"],
                description=scenario.get("description", ""),
                keywords=list(scenario.get("keywords", [])),
                urgencies=list(scenario.get("urgencies", [])),
                weights=self._normalize_weights(dict(scenario["weights"])),
                preferred_skills=list(scenario.get("preferred_skills", [])),
                preferred_inventory=list(scenario.get("preferred_inventory", [])),
                preferred_vehicles=list(scenario.get("preferred_vehicles", [])),
                urgency_weight_multipliers=urgency_multipliers,
            )
            for scenario in raw_config["scenarios"]
        }
        if default_scenario not in scenarios:
            raise DispatchMatchingError("Default dispatch scenario is not configured.")
        return default_scenario, fallback_threshold, scenarios

    def _normalize_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """Validate and normalize configured weights so they sum to one."""

        unknown_dimensions = set(weights).difference(SUPPORTED_SCORE_DIMENSIONS)
        if unknown_dimensions:
            names = ", ".join(sorted(unknown_dimensions))
            raise DispatchMatchingError(f"Unsupported dispatch score dimensions: {names}.")

        normalized_input: dict[str, float] = {}
        for key, value in weights.items():
            numeric_value = float(value)
            if numeric_value < 0:
                raise DispatchMatchingError("Dispatch scenario weights must not be negative.")
            normalized_input[key] = numeric_value

        total = sum(normalized_input.values())
        if total <= 0:
            raise DispatchMatchingError("Dispatch scenario weights must sum above zero.")
        return {key: value / total for key, value in normalized_input.items()}

    def _validate_urgency_multipliers(
        self,
        raw_multipliers: dict[str, Any],
    ) -> dict[str, dict[str, float]]:
        """Return validated positive urgency multipliers."""

        result: dict[str, dict[str, float]] = {}
        for urgency, multipliers in raw_multipliers.items():
            if not isinstance(multipliers, dict):
                raise DispatchMatchingError("Urgency weight multipliers must be objects.")
            unknown_dimensions = set(multipliers).difference(SUPPORTED_SCORE_DIMENSIONS)
            if unknown_dimensions:
                names = ", ".join(sorted(unknown_dimensions))
                raise DispatchMatchingError(
                    f"Unsupported urgency multiplier dimensions: {names}."
                )

            urgency_values: dict[str, float] = {}
            for key, value in multipliers.items():
                numeric_value = float(value)
                if numeric_value <= 0:
                    raise DispatchMatchingError(
                        "Urgency weight multipliers must be greater than zero."
                    )
                urgency_values[key] = numeric_value
            result[str(urgency)] = urgency_values
        return result


class ScenarioSelectionService:
    """Select a dispatch scenario from incident details."""

    def __init__(self, scenario_config: DispatchScenarioConfig | None = None) -> None:
        config = scenario_config or DispatchScenarioConfig()
        self.default_scenario, self.fallback_threshold, self.scenarios = config.load()

    def select_for_incident(self, incident: Incident) -> ScenarioSelection:
        """Select the best scenario for an incident using deterministic rules."""

        incident_terms = self._incident_terms(incident)
        best_scenario = self.scenarios[self.default_scenario]
        best_score = 0.0
        best_matches: list[str] = []

        for scenario in self.scenarios.values():
            score, matches = self._score_scenario(scenario, incident, incident_terms)
            if score > best_score:
                best_scenario = scenario
                best_score = score
                best_matches = matches

        confidence = min(1.0, best_score)
        if confidence < self.fallback_threshold:
            return ScenarioSelection(
                scenario=self.scenarios[self.default_scenario],
                confidence=confidence,
                matched_terms=best_matches,
            )
        return ScenarioSelection(
            scenario=best_scenario,
            confidence=confidence,
            matched_terms=best_matches,
        )

    def _incident_terms(self, incident: Incident) -> set[str]:
        """Return normalized text terms from incident details."""

        values: list[str] = [
            incident.title or "",
            incident.summary,
            incident.incident_type or "",
            incident.location_text or "",
            incident.casualties_text or "",
            incident.urgency,
            *(incident.needs or []),
        ]
        return set(_tokenize(" ".join(values)))

    def _score_scenario(
        self,
        scenario: DispatchScenario,
        incident: Incident,
        incident_terms: set[str],
    ) -> tuple[float, list[str]]:
        """Return scenario score and matched terms for an incident."""

        keyword_terms = set(_tokenize(" ".join(scenario.keywords)))
        matches = sorted(incident_terms.intersection(keyword_terms))
        keyword_score = min(1.0, len(matches) / max(1, min(4, len(keyword_terms))))
        urgency_score = 0.25 if incident.urgency in scenario.urgencies else 0.0
        return keyword_score + urgency_score, matches


class VolunteerMatchingService:
    """Score available volunteers and persist top recommendations."""

    def __init__(
        self,
        db: Session,
        scenario_service: ScenarioSelectionService | None = None,
    ) -> None:
        self.db = db
        self.scenario_service = scenario_service or ScenarioSelectionService()

    def recommend_for_incident(
        self,
        incident_id: int,
        limit: int = 3,
    ) -> DispatchRecommendationBatch:
        """Generate and persist top volunteer recommendations for an incident."""

        if limit <= 0:
            raise ValueError("Recommendation limit must be positive.")

        try:
            self._ensure_schema()
            incident = self.db.get(Incident, incident_id)
            if incident is None:
                raise ValueError("Incident was not found.")
            if incident.status != INCIDENT_STATUS_READY_FOR_DISPATCH:
                raise ValueError("Incident is not ready for dispatch matching.")

            selection = self.scenario_service.select_for_incident(incident)
            candidates = self._available_volunteers()
            scores = [
                self._score_volunteer(incident, volunteer, selection.scenario)
                for volunteer in candidates
            ]
            ranked_scores = sorted(
                scores,
                key=lambda score: score.total_score,
                reverse=True,
            )[:limit]
            self._delete_existing_recommendations(incident.id)
            recommendations = self._persist_recommendations(
                incident,
                selection,
                ranked_scores,
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise DispatchMatchingError("Volunteer matching failed.") from exc

        return DispatchRecommendationBatch(
            incident_id=incident.id,
            scenario=selection.scenario.name,
            scenario_confidence=selection.confidence,
            recommendations=recommendations,
        )

    def _ensure_schema(self) -> None:
        """Create known ORM tables when running without migrations in local/dev mode."""

        Base.metadata.create_all(bind=self.db.get_bind())

    def _available_volunteers(self) -> list[Volunteer]:
        """Return volunteers currently eligible for dispatch matching."""

        return (
            self.db.query(Volunteer)
            .filter(Volunteer.status == VOLUNTEER_STATUS_AVAILABLE)
            .order_by(Volunteer.id.asc())
            .all()
        )

    def _delete_existing_recommendations(self, incident_id: int) -> None:
        """Replace old recommendations for an incident with a fresh ranking."""

        self.db.query(DispatchRecommendation).filter(
            DispatchRecommendation.incident_id == incident_id,
            DispatchRecommendation.status == RECOMMENDATION_STATUS_RECOMMENDED,
        ).delete(synchronize_session=False)

    def _persist_recommendations(
        self,
        incident: Incident,
        selection: ScenarioSelection,
        ranked_scores: list[VolunteerScore],
    ) -> list[DispatchRecommendationResult]:
        """Persist ranked volunteer scores and return response DTOs."""

        results: list[DispatchRecommendationResult] = []
        for index, score in enumerate(ranked_scores, start=1):
            recommendation = DispatchRecommendation(
                incident_id=incident.id,
                volunteer_id=score.volunteer_id,
                scenario=selection.scenario.name,
                rank=index,
                total_score=score.total_score,
                score_breakdown=score.breakdown,
                status=RECOMMENDATION_STATUS_RECOMMENDED,
            )
            self.db.add(recommendation)
            self.db.flush()
            results.append(
                DispatchRecommendationResult(
                    recommendation_id=recommendation.id,
                    incident_id=incident.id,
                    volunteer_id=score.volunteer_id,
                    scenario=selection.scenario.name,
                    rank=index,
                    total_score=score.total_score,
                    score_breakdown=score.breakdown,
                )
            )
        return results

    def _score_volunteer(
        self,
        incident: Incident,
        volunteer: Volunteer,
        scenario: DispatchScenario,
    ) -> VolunteerScore:
        """Return weighted volunteer score for one incident and scenario."""

        dimension_scores = {
            "location": self._location_score(incident, volunteer),
            "skill_match": self._skill_score(incident, volunteer, scenario),
            "response_time": self._response_time_score(volunteer),
            "reliability": self._reliability_score(volunteer),
            "inventory_match": self._inventory_score(volunteer, scenario),
            "vehicle_match": self._vehicle_score(volunteer, scenario),
        }
        effective_weights = self._effective_weights(scenario, incident.urgency)
        total_score = sum(
            dimension_scores.get(key, 0.0) * weight
            for key, weight in effective_weights.items()
        )

        breakdown = {
            key: round(value, 6)
            for key, value in dimension_scores.items()
        }
        breakdown.update(
            {
                f"weight_{key}": round(value, 6)
                for key, value in effective_weights.items()
            }
        )
        return VolunteerScore(
            volunteer_id=volunteer.id,
            total_score=round(total_score, 6),
            breakdown=breakdown,
        )

    def _effective_weights(
        self,
        scenario: DispatchScenario,
        urgency: str,
    ) -> dict[str, float]:
        """Apply urgency multipliers and normalize the final situation weights."""

        urgency_multipliers = scenario.urgency_weight_multipliers.get(urgency, {})
        adjusted = {
            key: weight * urgency_multipliers.get(key, 1.0)
            for key, weight in scenario.weights.items()
        }
        total = sum(adjusted.values())
        if total <= 0:
            raise DispatchMatchingError("Effective dispatch weights must sum above zero.")
        return {key: value / total for key, value in adjusted.items()}

    def _location_score(self, incident: Incident, volunteer: Volunteer) -> float:
        """Score distance limits first, then service-area text matching."""

        metadata = volunteer.metadata_json or {}
        distance_km = _first_number(
            metadata.get("distance_km"),
            metadata.get("estimated_distance_km"),
        )
        max_distance_km = _first_number(metadata.get("max_distance_km"))

        if distance_km is not None and max_distance_km is not None:
            if max_distance_km <= 0 or distance_km > max_distance_km:
                return 0.0
            ratio = max(0.0, distance_km) / max_distance_km
            return max(0.2, min(1.0, 1.0 - (0.8 * ratio)))

        if distance_km is not None:
            if distance_km <= 2:
                return 1.0
            if distance_km >= 50:
                return 0.1
            return max(0.1, 1.0 - ((distance_km - 2) / 53.333333))

        location_text = (incident.location_text or "").strip().lower()
        service_areas = [
            str(area).lower()
            for area in metadata.get("service_areas", [])
        ]
        if not location_text or not service_areas:
            return 0.5
        if any(
            area and (area in location_text or location_text in area)
            for area in service_areas
        ):
            return 1.0

        location_terms = set(_tokenize(location_text))
        area_terms = set(_tokenize(" ".join(service_areas)))
        if not location_terms or not area_terms:
            return 0.25
        overlap = len(location_terms.intersection(area_terms)) / len(location_terms)
        return max(0.25, min(1.0, overlap))

    def _skill_score(
        self,
        incident: Incident,
        volunteer: Volunteer,
        scenario: DispatchScenario,
    ) -> float:
        """Score volunteer skills against scenario preferences and incident needs."""

        metadata = volunteer.metadata_json or {}
        volunteer_skills = set(_tokenize(" ".join(metadata.get("skills", []))))
        preferred_skills = set(_tokenize(" ".join(scenario.preferred_skills)))
        incident_terms = set(
            _tokenize(
                " ".join(
                    [
                        incident.incident_type or "",
                        *(incident.needs or []),
                    ]
                )
            )
        )
        target_terms = preferred_skills.union(incident_terms)
        if not volunteer_skills and not target_terms:
            return 0.5
        if not volunteer_skills:
            return 0.0
        if not target_terms:
            return 0.5
        return min(
            1.0,
            len(volunteer_skills.intersection(target_terms))
            / max(1, min(4, len(target_terms))),
        )

    def _inventory_score(
        self,
        volunteer: Volunteer,
        scenario: DispatchScenario,
    ) -> float:
        """Score the volunteer's declared inventory for the selected scenario."""

        metadata = volunteer.metadata_json or {}
        raw_inventory = [
            *(volunteer.inventory or []),
            *(metadata.get("inventory") or []),
        ]
        volunteer_items = {
            _normalize_item(item)
            for item in raw_inventory
            if str(item).strip()
        }
        target_items = {
            _normalize_item(item)
            for item in scenario.preferred_inventory
            if str(item).strip()
        }

        if not target_items:
            return 0.5
        if not volunteer_items:
            return 0.0

        matched_count = sum(
            1
            for target in target_items
            if any(_items_match(candidate, target) for candidate in volunteer_items)
        )
        return min(1.0, matched_count / max(1, min(3, len(target_items))))

    def _vehicle_score(
        self,
        volunteer: Volunteer,
        scenario: DispatchScenario,
    ) -> float:
        """Score the volunteer's vehicle against scenario preferences."""

        preferred = {
            _normalize_item(value)
            for value in scenario.preferred_vehicles
            if str(value).strip()
        }
        if not preferred:
            return 0.5

        metadata = volunteer.metadata_json or {}
        vehicle = _normalize_item(metadata.get("vehicle", ""))
        if not vehicle or vehicle in {"none", "no_vehicle", "without_vehicle"}:
            return 0.0
        if any(_items_match(vehicle, target) for target in preferred):
            return 1.0
        return 0.35

    def _response_time_score(self, volunteer: Volunteer) -> float:
        """Score estimated volunteer response time from metadata."""

        metadata = volunteer.metadata_json or {}
        minutes = _first_number(metadata.get("response_time_minutes"))
        if minutes is None:
            return 0.5
        if minutes <= 5:
            return 1.0
        if minutes >= 60:
            return 0.0
        return max(0.0, min(1.0, 1 - ((minutes - 5) / 55)))

    def _reliability_score(self, volunteer: Volunteer) -> float:
        """Return the explicit trust score with legacy metadata compatibility."""

        metadata = volunteer.metadata_json or {}
        legacy_score = _first_number(metadata.get("reliability_score"))
        trust_score = _first_number(volunteer.trust_score)

        if trust_score is not None and trust_score != 0.5:
            return max(0.0, min(1.0, trust_score))
        if legacy_score is not None:
            return max(0.0, min(1.0, legacy_score))
        if trust_score is not None:
            return max(0.0, min(1.0, trust_score))
        return 0.5


def _first_number(*values: Any) -> float | None:
    """Return the first value that can be parsed as a finite float."""

    for value in values:
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric == numeric and numeric not in {float("inf"), float("-inf")}:
            return numeric
    return None


def _normalize_item(value: Any) -> str:
    """Normalize profile item names to underscore-separated tokens."""

    return "_".join(_tokenize(str(value)))


def _items_match(candidate: str, target: str) -> bool:
    """Return whether two normalized inventory or vehicle labels overlap."""

    if candidate == target:
        return True
    candidate_tokens = set(candidate.split("_"))
    target_tokens = set(target.split("_"))
    if not candidate_tokens or not target_tokens:
        return False
    return target_tokens.issubset(candidate_tokens) or candidate_tokens.issubset(
        target_tokens
    )


def _tokenize(value: str) -> list[str]:
    """Normalize text into simple lowercase matching tokens."""

    return TOKEN_PATTERN.findall(value.lower().replace("-", "_"))
