"""Location helpers: demo city coordinates, Haversine distance, distance -> score."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

# Coordinates for the demo cities (latitude, longitude). No GIS / geocoding API needed.
CITY_COORDS: Dict[str, Tuple[float, float]] = {
    "Delhi": (28.6139, 77.2090),
    "Gurgaon": (28.4595, 77.0266),
    "Noida": (28.5355, 77.3910),
    "Meerut": (28.9845, 77.7064),
    "Jaipur": (26.9124, 75.7873),
    "Ludhiana": (30.9010, 75.8573),
    "Ahmedabad": (23.0225, 72.5714),
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Hyderabad": (17.3850, 78.4867),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Coimbatore": (11.0168, 76.9558),
    "Kolkata": (22.5726, 88.3639),
}

# lower-case alias -> canonical city name
CITY_ALIASES: Dict[str, str] = {name.lower(): name for name in CITY_COORDS}
CITY_ALIASES.update(
    {
        "new delhi": "Delhi",
        "ncr": "Delhi",
        "gurugram": "Gurgaon",
        "bangalore": "Bengaluru",
        "bombay": "Mumbai",
        "madras": "Chennai",
        "calcutta": "Kolkata",
    }
)

# (max_distance_km, score). Configurable: pass your own list to location_score().
DISTANCE_BANDS: List[Tuple[float, int]] = [
    (25, 100),
    (50, 90),
    (100, 75),
    (200, 50),
    (500, 30),
    (float("inf"), 10),
]


def resolve_city(name: Optional[str]) -> Optional[str]:
    """Return the canonical demo city name for `name` (or None if unknown)."""
    if not name:
        return None
    return CITY_ALIASES.get(name.strip().lower())


def city_coordinates(name: Optional[str]) -> Optional[Tuple[float, float]]:
    city = resolve_city(name)
    return CITY_COORDS[city] if city else None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def location_score(distance_km: float, bands: Optional[Sequence[Tuple[float, int]]] = None) -> int:
    """Convert a distance in km into a 0-100 score using `bands`."""
    bands = bands or DISTANCE_BANDS
    for max_km, score in bands:
        if distance_km <= max_km:
            return score
    return bands[-1][1]
