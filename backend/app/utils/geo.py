"""
Geo helpers for journey monitoring (Phase 7) and anomaly detection (Phase 8+).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone


EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two WGS84 points, in meters."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float | None:
    """Initial bearing from point 1 → point 2, degrees [0, 360)."""
    if lat1 == lat2 and lng1 == lng2:
        return None
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlng = math.radians(lng2 - lng1)
    x = math.sin(dlng) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(
        dlng
    )
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360.0) % 360.0


def ensure_aware(dt: datetime | None) -> datetime | None:
    """Make naive datetimes timezone-aware (assume UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compass_label(heading: float | None) -> str | None:
    if heading is None:
        return None
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((heading + 22.5) // 45) % 8
    return dirs[idx]
