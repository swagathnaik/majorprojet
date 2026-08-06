"""
Shared SOS creation helpers (Phases 9–11).
"""
from __future__ import annotations

from app.extensions import db
from app.models.journey import Journey
from app.models.location import LocationLog
from app.models.sos import SosAlert


def create_sos_alert(
    journey: Journey,
    *,
    sos_type: str,
    reason: str,
    lat: float | None = None,
    lng: float | None = None,
) -> tuple[SosAlert, list[dict]]:
    """
    Create an SOS alert, mark journey as sos, and notify all emergency contacts.
    sos_type: manual | automatic
    """
    if lat is None or lng is None:
        last = (
            LocationLog.query.filter_by(journey_id=journey.id)
            .order_by(LocationLog.recorded_at.desc())
            .first()
        )
        if last:
            lat = last.lat if lat is None else lat
            lng = last.lng if lng is None else lng

    alert = SosAlert(
        journey_id=journey.id,
        user_id=journey.user_id,
        type=sos_type,
        trigger_reason=reason,
        lat=lat,
        lng=lng,
        status="active",
    )
    journey.status = "sos"
    db.session.add(alert)
    db.session.flush()  # get alert.id before notify

    notifications: list[dict] = []
    try:
        from app.services.notify import notify_sos_all_contacts

        notifications = notify_sos_all_contacts(journey, alert)
    except Exception:
        # Never block SOS persistence on notify failure
        pass

    return alert, notifications
