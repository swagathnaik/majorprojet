"""
Journey monitoring – derive movement status from GPS logs (Phase 7).

Does NOT raise SOS. Phase 8 will use these metrics for anomaly rules.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app

from app.models.journey import Journey
from app.models.location import LocationLog
from app.utils.geo import (
    EARTH_RADIUS_M,
    bearing_deg,
    compass_label,
    ensure_aware,
    haversine_m,
)

# Speeds below this (m/s) count as stopped / near-stationary
MOVING_SPEED_MPS = 0.5
# Average walking speed used for rough ETA when destination coords exist
WALK_SPEED_MPS = 1.4


def build_monitoring_snapshot(journey: Journey) -> dict:
    """
    Compute a monitoring snapshot for a journey from its location logs.
    """
    now = datetime.now(timezone.utc)
    logs = (
        LocationLog.query.filter_by(journey_id=journey.id)
        .order_by(LocationLog.recorded_at.asc())
        .all()
    )

    started_at = ensure_aware(journey.started_at)
    duration_sec = 0
    if started_at:
        end_ref = ensure_aware(journey.ended_at) or now
        duration_sec = max(0, int((end_ref - started_at).total_seconds()))

    point_count = len(logs)
    last = logs[-1] if logs else None
    prev = logs[-2] if point_count >= 2 else None

    # --- Current location ---
    current = None
    if last:
        current = {
            "lat": last.lat,
            "lng": last.lng,
            "accuracy": last.accuracy,
            "recorded_at": last.recorded_at.isoformat() if last.recorded_at else None,
        }

    # --- Speed (prefer device speed, else derive from last two points) ---
    speed_mps = None
    speed_source = None
    if last and last.speed is not None and last.speed >= 0:
        speed_mps = float(last.speed)
        speed_source = "device"
    elif last and prev:
        t1 = ensure_aware(prev.recorded_at)
        t2 = ensure_aware(last.recorded_at)
        if t1 and t2:
            dt = (t2 - t1).total_seconds()
            if dt > 0:
                dist = haversine_m(prev.lat, prev.lng, last.lat, last.lng)
                speed_mps = dist / dt
                speed_source = "derived"

    # --- Heading / direction ---
    heading = None
    heading_source = None
    if last and last.heading is not None:
        heading = float(last.heading) % 360.0
        heading_source = "device"
    elif last and prev:
        heading = bearing_deg(prev.lat, prev.lng, last.lat, last.lng)
        heading_source = "derived" if heading is not None else None

    # --- Distance traveled (sum of segments) ---
    distance_m = 0.0
    for i in range(1, point_count):
        a, b = logs[i - 1], logs[i]
        distance_m += haversine_m(a.lat, a.lng, b.lat, b.lng)

    # --- Stop duration: how long current near-stationary streak has lasted ---
    stop_duration_sec = 0
    moving_threshold = MOVING_SPEED_MPS
    if last:
        # Walk backwards while points look stationary
        stop_start = ensure_aware(last.recorded_at) or now
        for i in range(point_count - 1, -1, -1):
            log = logs[i]
            spd = log.speed
            if spd is None and i > 0:
                prev_log = logs[i - 1]
                t1 = ensure_aware(prev_log.recorded_at)
                t2 = ensure_aware(log.recorded_at)
                if t1 and t2 and (t2 - t1).total_seconds() > 0:
                    spd = haversine_m(
                        prev_log.lat, prev_log.lng, log.lat, log.lng
                    ) / (t2 - t1).total_seconds()
                else:
                    spd = 0.0
            if spd is None:
                spd = 0.0
            if spd > moving_threshold:
                break
            stop_start = ensure_aware(log.recorded_at) or stop_start
        stop_duration_sec = max(0, int((now - stop_start).total_seconds()))

    # --- Movement status ---
    lost_signal_sec = int(current_app.config.get("LOST_SIGNAL_SEC", 75))
    seconds_since_update = None
    if last and last.received_at:
        # Use server receive time so skewed client clocks don't fake "lost signal"
        seconds_since_update = int(
            (now - ensure_aware(last.received_at)).total_seconds()
        )
    elif last and last.recorded_at:
        seconds_since_update = int(
            (now - ensure_aware(last.recorded_at)).total_seconds()
        )

    if journey.status == "paused":
        movement_status = "paused"
    elif journey.status == "sos":
        movement_status = "sos"
    elif not last:
        movement_status = "waiting_for_gps"
    elif seconds_since_update is not None and seconds_since_update > lost_signal_sec:
        movement_status = "signal_lost"
    elif speed_mps is not None and speed_mps > moving_threshold:
        movement_status = "moving"
    elif stop_duration_sec >= 15:
        movement_status = "stopped"
    else:
        movement_status = "slow_or_uncertain"

    # --- Route / destination deviation (prefer planned polyline) ---
    deviation_m = None
    distance_to_dest_m = None
    deviation_basis = None
    if last:
        route_pts = _expected_route_latlng(journey)
        if route_pts and len(route_pts) >= 2:
            deviation_m = round(
                _distance_to_polyline_m(last.lat, last.lng, route_pts),
                1,
            )
            deviation_basis = "expected_route"
        elif (
            journey.start_lat is not None
            and journey.start_lng is not None
            and journey.dest_lat is not None
            and journey.dest_lng is not None
        ):
            deviation_m = round(
                _distance_to_segment_m(
                    last.lat,
                    last.lng,
                    journey.start_lat,
                    journey.start_lng,
                    journey.dest_lat,
                    journey.dest_lng,
                ),
                1,
            )
            deviation_basis = "start_dest_line"

        if journey.dest_lat is not None and journey.dest_lng is not None:
            distance_to_dest_m = round(
                haversine_m(last.lat, last.lng, journey.dest_lat, journey.dest_lng),
                1,
            )

    # --- Time / location context ---
    hour_utc = now.hour
    # India-ish local approx (UTC+5:30) for demo context
    hour_ist = (hour_utc + 5) % 24
    minute_ist_bump = 1 if now.minute + 30 >= 60 else 0
    hour_ist = (hour_utc + 5 + minute_ist_bump) % 24
    is_night = hour_ist >= 22 or hour_ist < 5
    time_context = {
        "hour_ist_approx": hour_ist,
        "is_night": is_night,
        "label": "night" if is_night else "day",
    }

    # --- Rough ETA (walking assumption) – not a routing engine ---
    eta_sec = None
    eta_note = None
    if distance_to_dest_m is not None:
        eta_sec = int(distance_to_dest_m / WALK_SPEED_MPS)
        eta_note = "Rough estimate at ~5 km/h walking pace (not live traffic routing)."

    stop_threshold = int(current_app.config.get("STOP_THRESHOLD_SEC", 150))
    deviation_threshold = int(current_app.config.get("DEVIATION_THRESHOLD_M", 100))

    # Soft flags for Phase 7 UI only (Phase 8 will escalate carefully)
    flags = []
    if movement_status == "stopped" and stop_duration_sec >= stop_threshold:
        flags.append(
            {
                "type": "prolonged_stop",
                "message": f"Stopped for {stop_duration_sec}s (threshold {stop_threshold}s).",
                "level": "watch",
            }
        )
    if (
        deviation_m is not None
        and deviation_m >= deviation_threshold
        and journey.dest_lat is not None
    ):
        basis = "planned route" if deviation_basis == "expected_route" else "start→destination line"
        flags.append(
            {
                "type": "route_deviation",
                "message": f"~{int(deviation_m)}m off {basis} (threshold {deviation_threshold}m).",
                "level": "watch",
            }
        )
    if is_night and movement_status == "stopped" and stop_duration_sec >= max(60, stop_threshold // 2):
        flags.append(
            {
                "type": "night_stop",
                "message": f"Night-time stop lasting {stop_duration_sec}s.",
                "level": "watch",
            }
        )
    if movement_status == "signal_lost":
        flags.append(
            {
                "type": "lost_signal",
                "message": f"No GPS update for {seconds_since_update}s.",
                "level": "watch",
            }
        )

    return {
        "journey_id": journey.id,
        "journey_status": journey.status,
        "movement_status": movement_status,
        "current_location": current,
        "speed_mps": round(speed_mps, 3) if speed_mps is not None else None,
        "speed_kmh": round(speed_mps * 3.6, 2) if speed_mps is not None else None,
        "speed_source": speed_source,
        "heading_deg": round(heading, 1) if heading is not None else None,
        "heading_label": compass_label(heading),
        "heading_source": heading_source,
        "stop_duration_sec": stop_duration_sec,
        "distance_traveled_m": round(distance_m, 1),
        "distance_to_dest_m": distance_to_dest_m,
        "deviation_m": deviation_m,
        "deviation_basis": deviation_basis,
        "time_context": time_context,
        "journey_duration_sec": duration_sec,
        "eta_sec": eta_sec,
        "eta_note": eta_note,
        "point_count": point_count,
        "seconds_since_update": seconds_since_update,
        "thresholds": {
            "stop_threshold_sec": stop_threshold,
            "deviation_threshold_m": deviation_threshold,
            "lost_signal_sec": lost_signal_sec,
            "moving_speed_mps": moving_threshold,
        },
        "flags": flags,
        "computed_at": now.isoformat(),
        "note": "Real-time monitoring — anomaly rules escalate to safety verification, not silent SOS.",
    }


def _distance_to_segment_m(
    lat: float,
    lng: float,
    alat: float,
    alng: float,
    blat: float,
    blng: float,
) -> float:
    """
    Approximate distance from point to the start→dest segment using local
    equirectangular projection (good enough for city-scale walking trips).
    """
    import math as _math

    # meters per degree latitude
    lat_m = _math.radians(1) * EARTH_RADIUS_M
    x = (lng - alng) * _math.cos(_math.radians(alat)) * lat_m
    y = (lat - alat) * lat_m
    bx = (blng - alng) * _math.cos(_math.radians(alat)) * lat_m
    by = (blat - alat) * lat_m
    seg_len2 = bx * bx + by * by
    if seg_len2 == 0:
        return haversine_m(lat, lng, alat, alng)
    t = max(0.0, min(1.0, (x * bx + y * by) / seg_len2))
    proj_x = t * bx
    proj_y = t * by
    dx = x - proj_x
    dy = y - proj_y
    return _math.sqrt(dx * dx + dy * dy)


def _expected_route_latlng(journey: Journey) -> list[tuple[float, float]]:
    """Parse stored expected_route coordinates into [(lat, lng), ...]."""
    import json

    raw = journey.expected_route_json
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    coords = data.get("coordinates") if isinstance(data, dict) else None
    if not coords:
        return []
    points = []
    for c in coords:
        try:
            # GeoJSON order [lng, lat]
            points.append((float(c[1]), float(c[0])))
        except (TypeError, ValueError, IndexError):
            continue
    return points


def _distance_to_polyline_m(
    lat: float, lng: float, points: list[tuple[float, float]]
) -> float:
    """Min distance from point to any segment of the planned route."""
    if not points:
        return 0.0
    if len(points) == 1:
        return haversine_m(lat, lng, points[0][0], points[0][1])
    best = float("inf")
    for i in range(1, len(points)):
        a = points[i - 1]
        b = points[i]
        d = _distance_to_segment_m(lat, lng, a[0], a[1], b[0], b[1])
        if d < best:
            best = d
    return best
