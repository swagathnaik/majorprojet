"""
Rule-based anomaly detection (Phase 8).

Detects potentially unusual journey patterns. Does NOT claim crime/attack
detection and does NOT trigger SOS immediately.

Flow:
  monitoring metrics → rules → open Anomaly → pending SafetyCheck (Phase 9 UI)
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.anomaly import Anomaly
from app.models.journey import Journey
from app.models.location import LocationLog
from app.models.safety_check import SafetyCheck
from app.services.monitoring import build_monitoring_snapshot
from app.utils.geo import ensure_aware

# Cooldown after user clears / after same type detected
DEFAULT_COOLDOWN_SEC = 180
# Speed spike: current speed vs recent average (m/s)
SPEED_SPIKE_DELTA_MPS = 3.5
SPEED_SPIKE_MIN_MPS = 4.0


def evaluate_anomalies(journey: Journey, monitoring: dict | None = None) -> dict:
    """
    Run rule-based checks for an active journey.
    Returns { monitoring, open_anomalies, newly_created }.
    """
    if journey.status not in ("active",):
        # Only evaluate while actively tracking (not paused/sos/ended)
        mon = monitoring or build_monitoring_snapshot(journey)
        open_list = _open_anomalies(journey.id)
        return {
            "monitoring": mon,
            "open_anomalies": [a.to_dict() for a in open_list],
            "newly_created": [],
            "active_safety_check": _active_safety_check_dict(journey.id),
        }

    mon = monitoring or build_monitoring_snapshot(journey)
    candidates = _rule_candidates(journey, mon)
    newly = []

    for candidate in candidates:
        if _should_skip(journey.id, candidate["type"]):
            continue
        anomaly = _create_anomaly(journey, candidate)
        newly.append(anomaly.to_dict())

    open_list = _open_anomalies(journey.id)
    return {
        "monitoring": mon,
        "open_anomalies": [a.to_dict() for a in open_list],
        "newly_created": newly,
        "active_safety_check": _active_safety_check_dict(journey.id),
    }


def simulate_anomaly(journey: Journey, anomaly_type: str) -> dict:
    """
    Demo helper – force-create an anomaly type for viva demos.
    Requires DEMO_MODE=true.
    """
    if not current_app.config.get("DEMO_MODE", False):
        raise PermissionError("Demo mode is disabled.")

    allowed = {
        "prolonged_stop",
        "route_deviation",
        "lost_signal",
        "speed_spike",
    }
    if anomaly_type not in allowed:
        raise ValueError(f"Unknown anomaly type. Use one of: {', '.join(sorted(allowed))}")

    # Clear skip only for demo force – still avoid duplicate open of same type
    existing = (
        Anomaly.query.filter_by(journey_id=journey.id, type=anomaly_type, status="open")
        .first()
    )
    if existing:
        return {
            "anomaly": existing.to_dict(),
            "active_safety_check": _active_safety_check_dict(journey.id),
            "message": "Anomaly already open.",
        }

    anomaly = _create_anomaly(
        journey,
        {
            "type": anomaly_type,
            "severity": "medium",
            "details": {
                "simulated": True,
                "message": f"Demo simulated anomaly: {anomaly_type}",
            },
        },
    )
    return {
        "anomaly": anomaly.to_dict(),
        "active_safety_check": _active_safety_check_dict(journey.id),
        "message": "Simulated anomaly created.",
    }


def _rule_candidates(journey: Journey, mon: dict) -> list[dict]:
    stop_threshold = int(current_app.config.get("STOP_THRESHOLD_SEC", 150))
    deviation_threshold = int(current_app.config.get("DEVIATION_THRESHOLD_M", 100))
    lost_signal_sec = int(current_app.config.get("LOST_SIGNAL_SEC", 75))

    candidates = []

    # Rule 1 – prolonged stop (must have been moving earlier in journey)
    if (
        mon.get("movement_status") == "stopped"
        and mon.get("stop_duration_sec", 0) >= stop_threshold
        and _had_recent_motion(journey.id)
    ):
        candidates.append(
            {
                "type": "prolonged_stop",
                "severity": "medium",
                "details": {
                    "stop_duration_sec": mon.get("stop_duration_sec"),
                    "threshold_sec": stop_threshold,
                    "message": "Unexpected prolonged inactivity after movement.",
                },
            }
        )

    # Rule 2 – significant route deviation (needs dest coords)
    deviation = mon.get("deviation_m")
    if (
        deviation is not None
        and deviation >= deviation_threshold
        and journey.dest_lat is not None
        and journey.dest_lng is not None
    ):
        candidates.append(
            {
                "type": "route_deviation",
                "severity": "medium",
                "details": {
                    "deviation_m": deviation,
                    "threshold_m": deviation_threshold,
                    "message": "Significant deviation from expected start→destination path.",
                },
            }
        )

    # Rule 3 – lost GPS updates while journey active
    if mon.get("movement_status") == "signal_lost":
        candidates.append(
            {
                "type": "lost_signal",
                "severity": "high",
                "details": {
                    "seconds_since_update": mon.get("seconds_since_update"),
                    "threshold_sec": lost_signal_sec,
                    "message": "Location updates stopped unexpectedly.",
                },
            }
        )

    # Rule 4 – abnormal speed spike
    spike = _detect_speed_spike(journey.id, mon)
    if spike:
        candidates.append(
            {
                "type": "speed_spike",
                "severity": "low",
                "details": spike,
            }
        )

    return candidates


def _had_recent_motion(journey_id: int) -> bool:
    """True if any earlier point looked like walking/moving."""
    logs = (
        LocationLog.query.filter_by(journey_id=journey_id)
        .order_by(LocationLog.recorded_at.asc())
        .all()
    )
    for log in logs:
        if log.speed is not None and log.speed > 0.5:
            return True
    # If we have multiple spaced points with distance, treat as motion
    if len(logs) >= 3:
        return True
    return False


def _detect_speed_spike(journey_id: int, mon: dict) -> dict | None:
    current = mon.get("speed_mps")
    if current is None or current < SPEED_SPIKE_MIN_MPS:
        return None

    logs = (
        LocationLog.query.filter_by(journey_id=journey_id)
        .order_by(LocationLog.recorded_at.desc())
        .limit(8)
        .all()
    )
    recent_speeds = [log.speed for log in logs[1:] if log.speed is not None and log.speed >= 0]
    if len(recent_speeds) < 2:
        return None
    avg = sum(recent_speeds) / len(recent_speeds)
    if current - avg >= SPEED_SPIKE_DELTA_MPS:
        return {
            "current_speed_mps": current,
            "recent_avg_mps": round(avg, 3),
            "delta_mps": round(current - avg, 3),
            "message": "Sudden speed increase detected.",
        }
    return None


def _should_skip(journey_id: int, anomaly_type: str) -> bool:
    """Skip if same type already open, or cleared within cooldown."""
    open_same = (
        Anomaly.query.filter_by(
            journey_id=journey_id, type=anomaly_type, status="open"
        ).first()
    )
    if open_same:
        return True

    # Any pending safety check → don't pile on more anomalies yet
    pending = (
        SafetyCheck.query.filter_by(journey_id=journey_id, status="pending").first()
    )
    if pending:
        return True

    cooldown = int(
        current_app.config.get("ANOMALY_COOLDOWN_SEC", DEFAULT_COOLDOWN_SEC)
    )
    since = datetime.now(timezone.utc) - timedelta(seconds=cooldown)
    recent = (
        Anomaly.query.filter_by(journey_id=journey_id, type=anomaly_type)
        .filter(Anomaly.cleared_at.isnot(None))
        .order_by(Anomaly.cleared_at.desc())
        .first()
    )
    if recent and ensure_aware(recent.cleared_at) and ensure_aware(recent.cleared_at) >= since:
        return True

    return False


def _create_anomaly(journey: Journey, candidate: dict) -> Anomaly:
    anomaly = Anomaly(
        journey_id=journey.id,
        type=candidate["type"],
        severity=candidate.get("severity", "medium"),
        status="open",
        details_json=json.dumps(candidate.get("details") or {}),
    )
    db.session.add(anomaly)
    db.session.flush()

    # Phase 9 will present this to the user – created now so the gate exists
    check = SafetyCheck(
        anomaly_id=anomaly.id,
        journey_id=journey.id,
        status="pending",
        countdown_seconds=int(current_app.config.get("SOS_COUNTDOWN_SEC", 20)),
    )
    db.session.add(check)
    db.session.commit()
    return anomaly


def _open_anomalies(journey_id: int) -> list[Anomaly]:
    return (
        Anomaly.query.filter_by(journey_id=journey_id, status="open")
        .order_by(Anomaly.detected_at.desc())
        .all()
    )


def _active_safety_check_dict(journey_id: int) -> dict | None:
    from app.services.safety_verification import get_pending_check, safety_check_payload

    check = get_pending_check(journey_id)
    return safety_check_payload(check) if check else None
