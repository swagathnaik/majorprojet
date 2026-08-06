"""
Safety verification – "Are you safe?" gate (Phase 9).

YES → clear anomaly, continue journey
NEED HELP → SOS immediately
NO RESPONSE → countdown → automatic SOS (timeout)
Cancel during countdown → treat as safe
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.models.anomaly import Anomaly
from app.models.journey import Journey
from app.models.safety_check import SafetyCheck
from app.services.sos_service import create_sos_alert
from app.utils.geo import ensure_aware


def get_pending_check(journey_id: int) -> SafetyCheck | None:
    return (
        SafetyCheck.query.filter_by(journey_id=journey_id, status="pending")
        .order_by(SafetyCheck.prompted_at.desc())
        .first()
    )


def safety_check_payload(check: SafetyCheck) -> dict:
    """Enrich safety check with anomaly info + timing for the UI."""
    data = check.to_dict()
    anomaly = db.session.get(Anomaly, check.anomaly_id)
    data["anomaly"] = anomaly.to_dict() if anomaly else None

    response_window = int(current_app.config.get("SAFETY_RESPONSE_SEC", 40))
    countdown = check.countdown_seconds or int(
        current_app.config.get("SOS_COUNTDOWN_SEC", 20)
    )
    prompted = ensure_aware(check.prompted_at)
    now = datetime.now(timezone.utc)
    elapsed = int((now - prompted).total_seconds()) if prompted else 0

    data["response_window_sec"] = response_window
    data["countdown_seconds"] = countdown
    data["elapsed_sec"] = elapsed
    data["response_deadline_sec"] = max(0, response_window - elapsed)
    return data


def respond_to_safety_check(
    check: SafetyCheck,
    journey: Journey,
    response: str,
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> dict:
    """
    Handle user response: safe | need_help
    """
    if check.status != "pending":
        raise ValueError(f"Safety check is already {check.status}.")

    response = (response or "").strip().lower()
    now = datetime.now(timezone.utc)

    if response == "safe":
        return _mark_safe(check, journey, now, note="User confirmed safe.")

    if response == "need_help":
        check.status = "need_help"
        check.response = "need_help"
        check.responded_at = now
        anomaly = db.session.get(Anomaly, check.anomaly_id)
        if anomaly and anomaly.status == "open":
            anomaly.status = "escalated"
        alert = create_sos_alert(
            journey,
            sos_type="manual",
            reason="User selected I NEED HELP after anomaly verification",
            lat=lat,
            lng=lng,
        )
        db.session.commit()
        return {
            "message": "Help requested — SOS triggered.",
            "safety_check": safety_check_payload(check),
            "sos": alert.to_dict(),
            "journey": journey.to_dict(),
        }

    raise ValueError("response must be 'safe' or 'need_help'.")


def cancel_countdown(
    check: SafetyCheck,
    journey: Journey,
) -> dict:
    """User cancels during countdown → treat as verified safe."""
    if check.status != "pending":
        raise ValueError(f"Safety check is already {check.status}.")
    now = datetime.now(timezone.utc)
    return _mark_safe(
        check,
        journey,
        now,
        note="User cancelled countdown — marked safe.",
        cancelled=True,
    )


def timeout_safety_check(
    check: SafetyCheck,
    journey: Journey,
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> dict:
    """
    Countdown reached zero with no response → automatic SOS.
    """
    if check.status != "pending":
        raise ValueError(f"Safety check is already {check.status}.")

    now = datetime.now(timezone.utc)
    check.status = "timeout"
    check.responded_at = now
    check.response = None

    anomaly = db.session.get(Anomaly, check.anomaly_id)
    if anomaly and anomaly.status == "open":
        anomaly.status = "escalated"

    reason = "Automatic SOS: no response after anomaly safety verification"
    if anomaly:
        reason = f"{reason} ({anomaly.type})"

    alert = create_sos_alert(
        journey,
        sos_type="automatic",
        reason=reason,
        lat=lat,
        lng=lng,
    )
    db.session.commit()
    return {
        "message": "Automatic SOS triggered.",
        "safety_check": safety_check_payload(check),
        "sos": alert.to_dict(),
        "journey": journey.to_dict(),
    }


def _mark_safe(
    check: SafetyCheck,
    journey: Journey,
    now: datetime,
    *,
    note: str,
    cancelled: bool = False,
) -> dict:
    check.status = "cancelled" if cancelled else "safe"
    check.response = "safe"
    check.responded_at = now

    anomaly = db.session.get(Anomaly, check.anomaly_id)
    if anomaly and anomaly.status == "open":
        anomaly.status = "cleared"
        anomaly.cleared_at = now

    # Clear other open anomalies on this journey (false-alarm reset)
    others = Anomaly.query.filter_by(journey_id=journey.id, status="open").all()
    for a in others:
        a.status = "cleared"
        a.cleared_at = now

    # Cancel any other pending checks
    pending = SafetyCheck.query.filter_by(
        journey_id=journey.id, status="pending"
    ).all()
    for p in pending:
        if p.id == check.id:
            continue
        p.status = "cancelled"
        p.responded_at = now
        p.response = "safe"

    db.session.commit()
    return {
        "message": note,
        "safety_check": safety_check_payload(check),
        "sos": None,
        "journey": journey.to_dict(),
    }
