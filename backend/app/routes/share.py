"""
Public share / trusted-contact live tracking (no JWT).
GET /api/share/<share_token>
"""
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from app.extensions import db
from app.models.journey import Journey
from app.models.location import LocationLog
from app.models.sos import SosAlert
from app.models.user import User
from app.models.contact import EmergencyContact
from app.services.monitoring import build_monitoring_snapshot

share_bp = Blueprint("share", __name__)


@share_bp.get("/<share_token>")
def public_share(share_token: str):
    """
    Secure tracking link for trusted contacts.
    Returns live location, SOS status, reason, and time — no traveler login.
    """
    token = (share_token or "").strip()
    if not token or len(token) < 16:
        return jsonify({"error": "Invalid share link."}), 404

    journey = Journey.query.filter_by(share_token=token).first()
    if not journey:
        return jsonify({"error": "Journey link not found or expired."}), 404

    user = db.session.get(User, journey.user_id)
    contact = None
    if journey.active_contact_id:
        contact = db.session.get(EmergencyContact, journey.active_contact_id)

    logs = (
        LocationLog.query.filter_by(journey_id=journey.id)
        .order_by(LocationLog.recorded_at.asc())
        .all()
    )
    if len(logs) > 200:
        logs = logs[-200:]

    sos = (
        SosAlert.query.filter_by(journey_id=journey.id, status="active")
        .order_by(SosAlert.created_at.desc())
        .first()
    )
    monitoring = None
    try:
        monitoring = build_monitoring_snapshot(journey)
    except Exception:
        monitoring = None

    first_name = (user.name or "Traveler").split()[0] if user else "Traveler"

    return (
        jsonify(
            {
                "journey": {
                    "id": journey.id,
                    "status": journey.status,
                    "dest_label": journey.dest_label,
                    "dest_lat": journey.dest_lat,
                    "dest_lng": journey.dest_lng,
                    "start_lat": journey.start_lat,
                    "start_lng": journey.start_lng,
                    "started_at": journey.started_at.isoformat()
                    if journey.started_at
                    else None,
                    "ended_at": journey.ended_at.isoformat() if journey.ended_at else None,
                    "expected_route": journey.to_dict().get("expected_route"),
                },
                "traveler": {"first_name": first_name},
                "contact": (
                    {"name": contact.name, "relationship": contact.relationship}
                    if contact
                    else None
                ),
                "locations": [log.to_dict() for log in logs],
                "location_count": len(logs),
                "monitoring": monitoring,
                "sos": sos.to_dict() if sos else None,
                "emergency": {
                    "call_112": "112",
                    "note": "Optional India emergency number — SafeRoute does not auto-dial 112.",
                },
                "polled_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        200,
    )
