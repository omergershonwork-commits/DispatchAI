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


class DispatchMatchingError(RuntimeError):
    """Raised when volunteer matching cannot be completed."""


@dataclass(frozen=True)
class DispatchScenario:
    """Scenario configuration used for deterministic volunteer scoring."""

    name: str
    """Stable scenario identifier."""

    description: str
    """Human-readable scenario description."""

    keywords: list[str]
    """Keywords used by the scenario selector."""

    urgencies: list[str]
    """Urgency labels associated with the scenario."""

    weights: dict[str, float]
    """Normalized score weights."""

    preferred_skills: list[str]
    """Volunteer skills that fit the scenario."""


@dataclass(frozen=True)
class ScenarioSelection:
    """Selected scenario and confidence for an incident."""

    scenario: DispatchScenario
    """Selected dispatch scenario."""

    confidence: float
    """Selection confidence from zero to one."""

    matched_terms: list[str]
    """Terms that influenced the scenario selection."""


@dataclass(frozen=True)
class VolunteerScore:
    """Computed score for one volunteer candidate."""

    volunteer_id: int
    """Volunteer identifier."""

    total_score: float
    """Final weighted score from zero to one."""

    breakdown: dict[str, float]
    """Per-dimension scoring details."""


@dataclass(frozen=True)
class DispatchRecommendationResult:
    """Persisted top volunteer recommendation result."""

    recommendation_id: int
    """Recommendation row identifier."""

    incident_id: int
    """Incident being matched."""

    volunteer_id: int
    """Recommended volunteer."""

    scenario: str
    """Scenario used for scoring."""

    rank: int
    """One-based rank in the recommendation list."""

    total_score: float
    """Final weighted score."""

    score_breakdown: dict[str, float]
    """Per-dimension scoring details."""


@dataclass(frozen=True)
class DispatchRecommendationBatch:
    """Output returned after generating recommendations for one incident."""

    incident_id: int
    """Incident that was matched."""

    scenario: str
    """Selected scenario name."""

    scenario_confidence: float
    """Scenario selection confidence."""

    recommendations: list[DispatchRecommendationResult]
    """Persisted recommendations ordered by rank."""


class DispatchScenarioConfig:
    """Load and validate dispatch scenario configuration."""

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        """Create a scenario config loader."""

        self.config_path = config_path

    def load(self) -> tuple[str, float, dict[str, DispatchScenario]]:
        """Return default scenario, confidence threshold, and scenario map."""

        raw_config = json.loads(self.config_path.read_text(encoding="utf-8"))
        default_scenario = raw_config["default_scenario"]
        fallback_threshold = float(raw_config.get("fallback_confidence_threshold", 0.7))
        scenarios = {
            scenario["name"]: DispatchScenario(
                name=scenario["name"],
                description=scenario.get("description", ""),
                keywords=list(scenario.get("keywords", [])),
                urgencies=list(scenario.get("urgencies", [])),
                weights=self._normalize_weights(dict(scenario["weights"])),
                preferred_skills=list(scenario.get("preferred_skills", [])),
            )
            for scenario in raw_config["scenarios"]
        }
        if default_scenario not in scenarios:
            raise DispatchMatchingError("Default dispatch scenario is not configured.")
        return default_scenario, fallback_threshold, scenarios

    def _normalize_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """Normalize configured weights so they sum to one."""

        total = sum(float(value) for value in weights.values())
        if total <= 0:
            raise DispatchMatchingError("Dispatch scenario weights must sum above zero.")
        return {key: float(value) / total for key, value in weights.items()}


class ScenarioSelectionService:
    """Select a dispatch scenario from incident details."""

    def __init__(self, scenario_config: DispatchScenarioConfig | None = None) -> None:
        """Create a scenario selection service."""

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
        return ScenarioSelection(scenario=best_scenario, confidence=confidence, matched_terms=best_matches)

    def _incident_terms(self, incident: Incident) -> set[str]:
        """Return normalized text terms from incident details."""

        values: list[str] = [
            incident.summary,
            incident.incident_type or "",
            incident.location_text or "",
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

    def __init__(self, db: Session, scenario_service: ScenarioSelectionService | None = None) -> None:
        """Create a volunteer matching service bound to one DB session."""

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
            ranked_scores = sorted(scores, key=lambda score: score.total_score, reverse=True)[:limit]
            self._delete_existing_recommendations(incident.id)
            recommendations = self._persist_recommendations(incident, selection, ranked_scores)
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

        breakdown = {
            "location": self._location_score(incident, volunteer),
            "availability": 1.0,
            "skill_match": self._skill_score(incident, volunteer, scenario),
            "response_time": self._response_time_score(volunteer),
            "reliability": self._reliability_score(volunteer),
        }
        total_score = sum(
            breakdown[key] * scenario.weights.get(key, 0.0)
            for key in breakdown
        )
        return VolunteerScore(
            volunteer_id=volunteer.id,
            total_score=round(total_score, 6),
            breakdown={key: round(value, 6) for key, value in breakdown.items()},
        )

    def _location_score(self, incident: Incident, volunteer: Volunteer) -> float:
        """Score volunteer service area against incident free-text location."""

        location_text = (incident.location_text or "").strip().lower()
        metadata = volunteer.metadata_json or {}
        service_areas = [str(area).lower() for area in metadata.get("service_areas", [])]
        if not location_text or not service_areas:
            return 0.5
        if any(area and (area in location_text or location_text in area) for area in service_areas):
            return 1.0
        location_terms = set(_tokenize(location_text))
        area_terms = set(_tokenize(" ".join(service_areas)))
        if not location_terms or not area_terms:
            return 0.25
        overlap = len(location_terms.intersection(area_terms)) / len(location_terms)
        return max(0.25, min(1.0, overlap))

    def _skill_score(self, incident: Incident, volunteer: Volunteer, scenario: DispatchScenario) -> float:
        """Score volunteer skills against scenario preferences and incident needs."""

        metadata = volunteer.metadata_json or {}
        volunteer_skills = set(_tokenize(" ".join(metadata.get("skills", []))))
        preferred_skills = set(_tokenize(" ".join(scenario.preferred_skills)))
        incident_terms = set(_tokenize(" ".join([incident.incident_type or "", *(incident.needs or [])])))
        target_terms = preferred_skills.union(incident_terms)
        if not volunteer_skills and not target_terms:
            return 0.5
        if not volunteer_skills:
            return 0.0
        if not target_terms:
            return 0.5
        return min(1.0, len(volunteer_skills.intersection(target_terms)) / max(1, len(target_terms)))

    def _response_time_score(self, volunteer: Volunteer) -> float:
        """Score estimated volunteer response time from metadata."""

        metadata = volunteer.metadata_json or {}
        minutes = metadata.get("response_time_minutes")
        if minutes is None:
            return 0.5
        try:
            response_minutes = float(minutes)
        except (TypeError, ValueError):
            return 0.5
        if response_minutes <= 5:
            return 1.0
        if response_minutes >= 60:
            return 0.0
        return max(0.0, min(1.0, 1 - ((response_minutes - 5) / 55)))

    def _reliability_score(self, volunteer: Volunteer) -> float:
        """Return volunteer reliability score from metadata."""

        metadata = volunteer.metadata_json or {}
        reliability = metadata.get("reliability_score", 0.5)
        try:
            return max(0.0, min(1.0, float(reliability)))
        except (TypeError, ValueError):
            return 0.5


def _tokenize(value: str) -> list[str]:
    """Normalize text into simple lowercase matching tokens."""

    return TOKEN_PATTERN.findall(value.lower().replace("-", "_"))
