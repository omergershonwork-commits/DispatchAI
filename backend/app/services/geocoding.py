import json
import math
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings


class GeocodingError(RuntimeError):
    """Raised when a location cannot be resolved safely."""


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float
    display_name: str | None = None
    source: str = "geocoder"

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90.")
        if not -180 <= self.longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180.")


class GeocodingService:
    """Resolve text addresses through a configurable Nominatim-compatible endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        user_agent: str | None = None,
        timeout_seconds: float | None = None,
        country_codes: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.base_url = (base_url or settings.geocoding_base_url).rstrip("/")
        self.user_agent = user_agent or settings.geocoding_user_agent
        self.timeout_seconds = timeout_seconds or settings.geocoding_timeout_seconds
        self.country_codes = country_codes if country_codes is not None else settings.geocoding_country_codes
        self.enabled = settings.geocoding_enabled if enabled is None else enabled

    def geocode(self, address: str) -> GeoPoint | None:
        clean_address = " ".join(address.strip().split())
        if not clean_address or not self.enabled:
            return None

        params = {
            "q": clean_address,
            "format": "jsonv2",
            "limit": "1",
            "addressdetails": "1",
        }
        if self.country_codes.strip():
            params["countrycodes"] = self.country_codes.strip()

        request = Request(
            f"{self.base_url}/search?{urlencode(params)}",
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise GeocodingError("Geocoding request failed.") from exc

        if not isinstance(payload, list) or not payload:
            return None
        item = payload[0]
        try:
            return GeoPoint(
                latitude=float(item["lat"]),
                longitude=float(item["lon"]),
                display_name=str(item.get("display_name") or clean_address),
                source="geocoded_address",
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GeocodingError("Geocoding response was invalid.") from exc


def haversine_distance_km(first: GeoPoint, second: GeoPoint) -> float:
    """Return straight-line distance in kilometers between two WGS84 points."""

    earth_radius_km = 6371.0088
    lat1 = math.radians(first.latitude)
    lat2 = math.radians(second.latitude)
    delta_lat = math.radians(second.latitude - first.latitude)
    delta_lon = math.radians(second.longitude - first.longitude)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return earth_radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
