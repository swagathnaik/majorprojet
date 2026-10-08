"""
Police Station Data Service.
Loads curated police stations with verified emergency contact numbers,
calculates proximity to user coordinates, and provides nearest station lookups.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from app.utils.geo import haversine_m

logger = logging.getLogger(__name__)

_DATA_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "police_stations.json")
)
_POLICE_STATIONS_CACHE: Optional[List[Dict[str, Any]]] = None


def load_police_stations() -> List[Dict[str, Any]]:
    """Loads police stations from the JSON dataset."""
    global _POLICE_STATIONS_CACHE
    if _POLICE_STATIONS_CACHE is not None:
        return _POLICE_STATIONS_CACHE

    stations: List[Dict[str, Any]] = []
    if os.path.exists(_DATA_FILE):
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                stations = json.load(f)
            logger.info("Loaded %d police stations from %s", len(stations), _DATA_FILE)
        except Exception as e:
            logger.error("Failed to load police stations: %s", e)
    else:
        logger.warning("Police stations data file not found at %s", _DATA_FILE)

    _POLICE_STATIONS_CACHE = stations
    return _POLICE_STATIONS_CACHE


def format_distance(distance_m: float) -> str:
    """Format meters into a clean user-facing string (e.g. 350 m or 2.4 km)."""
    if distance_m < 1000:
        return f"{int(round(distance_m))} m"
    return f"{distance_m / 1000.0:.1f} km"


def get_all_police_stations(
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    max_radius_km: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Returns all police stations, optionally sorted by proximity to (user_lat, user_lng).
    """
    stations = load_police_stations()
    results = []

    for s in stations:
        station_copy = dict(s)
        if user_lat is not None and user_lng is not None:
            dist_m = haversine_m(user_lat, user_lng, s["lat"], s["lng"])
            dist_km = dist_m / 1000.0
            if max_radius_km is not None and dist_km > max_radius_km:
                continue
            station_copy["distance_m"] = round(dist_m, 1)
            station_copy["distance_km"] = round(dist_km, 2)
            station_copy["distance_str"] = format_distance(dist_m)
        results.append(station_copy)

    if user_lat is not None and user_lng is not None:
        results.sort(key=lambda x: x.get("distance_m", float("inf")))

    return results


def get_nearest_police_station(
    user_lat: float, user_lng: float
) -> Optional[Dict[str, Any]]:
    """Returns the single closest police station to the given coordinates."""
    stations = get_all_police_stations(user_lat, user_lng)
    return stations[0] if stations else None
