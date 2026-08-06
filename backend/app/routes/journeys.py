"""
Journey routes – Safe Journey Mode (Phase 5) + GPS (Phase 4).
"""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.journey import Journey
from app.models.location import LocationLog
from app.models.contact import EmergencyContact
from app.services.monitoring import build_monitoring_snapshot
from app.services.anomaly_engine import evaluate_anomalies, simulate_anomaly
from app.services.sos_service import create_sos_alert

journeys_bp = Blueprint("journeys", __name__)


def _user_id() -> int:
    return int(get_jwt_identity())


def _parse_iso_datetime(value):
    """Parse client ISO timestamp; fall back to UTC now."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)


def _optional_float(data, key):
    if data.get(key) is None or data.get(key) == "":
        return None
    try:
        return float(data[key])
    except (TypeError, ValueError):
        return None


def _owned_journey(journey_id: int, user_id: int):
    return Journey.query.filter_by(id=journey_id, user_id=user_id).first()


def _active_journey(user_id: int):
    return (
        Journey.query.filter_by(user_id=user_id)
        .filter(Journey.status.in_(["active", "paused", "sos"]))
        .order_by(Journey.started_at.desc())
        .first()
    )


def _journey_payload(journey: Journey) -> dict:
    """Journey dict plus selected contact summary (for UI)."""
    payload = journey.to_dict()
    contact = None
    if journey.active_contact_id:
        contact = db.session.get(EmergencyContact, journey.active_contact_id)
    payload["contact"] = (
        {
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "relationship": contact.relationship,
            "is_primary": contact.is_primary,
        }
        if contact
        else None
    )
    try:
        from app.services.notify import journey_share_url

        payload["share_url"] = journey_share_url(journey)
    except Exception:
        payload["share_url"] = None
    return payload


def _set_status(journey: Journey, status: str):
    journey.status = status
    if status in ("ended", "cancelled"):
        journey.ended_at = datetime.now(timezone.utc)


@journeys_bp.get("/active")
@jwt_required()
def get_active_journey():
    """Return the user's current in-progress journey, if any."""
    journey = _active_journey(_user_id())
    if not journey:
        return jsonify({"journey": None}), 200
    return jsonify({"journey": _journey_payload(journey)}), 200


@journeys_bp.post("")
@jwt_required()
def start_journey():
    """
    Start Safe Journey Mode.
    Body: {
      dest_label (required),
      active_contact_id (required if user has contacts – recommended),
      start_lat, start_lng,
      dest_lat?, dest_lng?
    }
    """
    user_id = _user_id()
    existing = _active_journey(user_id)
    if existing:
        return (
            jsonify(
                {
                    "error": "You already have an active journey. End or cancel it first.",
                    "journey": _journey_payload(existing),
                }
            ),
            409,
        )

    data = request.get_json(silent=True) or {}
    dest_label = (data.get("dest_label") or "").strip()
    if not dest_label:
        return jsonify({"error": "Destination is required (dest_label)."}), 400

    contacts = EmergencyContact.query.filter_by(user_id=user_id).all()
    if not contacts:
        return (
            jsonify(
                {
                    "error": "Add at least one emergency contact before starting a Safe Journey."
                }
            ),
            400,
        )

    contact_id = data.get("active_contact_id")
    if contact_id is None or contact_id == "":
        primary = next((c for c in contacts if c.is_primary), contacts[0])
        contact_id = primary.id
    else:
        contact_id = int(contact_id)
        contact = next((c for c in contacts if c.id == contact_id), None)
        if not contact:
            return jsonify({"error": "Emergency contact not found."}), 400

    start_lat = _optional_float(data, "start_lat")
    start_lng = _optional_float(data, "start_lng")
    dest_lat = _optional_float(data, "dest_lat")
    dest_lng = _optional_float(data, "dest_lng")

    route_json = None
    if data.get("expected_route"):
        import json as _json

        try:
            route_json = _json.dumps(data.get("expected_route"))
        except (TypeError, ValueError):
            route_json = None

    journey = Journey(
        user_id=user_id,
        status="active",
        start_lat=start_lat,
        start_lng=start_lng,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
        dest_label=dest_label,
        expected_route_json=route_json,
        active_contact_id=contact_id,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(journey)
    db.session.commit()

    contact = db.session.get(EmergencyContact, contact_id)
    share = None
    try:
        from app.services.notify import notify_journey_started, journey_share_url

        share = notify_journey_started(journey, contact)
        share_url = journey_share_url(journey)
    except Exception:
        from app.services.notify import journey_share_url

        share_url = journey_share_url(journey)
        share = {"share_url": share_url, "delivery": {"status": "partial"}}

    payload = _journey_payload(journey)
    payload["share_url"] = share_url

    return (
        jsonify(
            {
                "message": "Safe Journey started. Tracking link shared with trusted contact.",
                "journey": payload,
                "share": share,
            }
        ),
        201,
    )


@journeys_bp.get("/<int:journey_id>")
@jwt_required()
def get_journey(journey_id: int):
    journey = _owned_journey(journey_id, _user_id())
    if not journey:
        return jsonify({"error": "Journey not found."}), 404
    return jsonify({"journey": _journey_payload(journey)}), 200


@journeys_bp.post("/<int:journey_id>/pause")
@jwt_required()
def pause_journey(journey_id: int):
    """Pause tracking – GPS uploads stop until resume."""
    journey = _owned_journey(journey_id, _user_id())
    if not journey:
        return jsonify({"error": "Journey not found."}), 404
    if journey.status != "active":
        return jsonify({"error": f"Cannot pause a journey that is {journey.status}."}), 400

    journey.status = "paused"
    db.session.commit()
    return jsonify({"message": "Journey paused.", "journey": _journey_payload(journey)}), 200


@journeys_bp.post("/<int:journey_id>/resume")
@jwt_required()
def resume_journey(journey_id: int):
    """Resume a paused journey."""
    journey = _owned_journey(journey_id, _user_id())
    if not journey:
        return jsonify({"error": "Journey not found."}), 404
    if journey.status != "paused":
        return jsonify({"error": f"Cannot resume a journey that is {journey.status}."}), 400

    journey.status = "active"
    db.session.commit()
    return jsonify({"message": "Journey resumed.", "journey": _journey_payload(journey)}), 200


@journeys_bp.post("/<int:journey_id>/end")
@jwt_required()
def end_journey(journey_id: int):
    """Successfully end an active or paused journey."""
    journey = _owned_journey(journey_id, _user_id())
    if not journey:
        return jsonify({"error": "Journey not found."}), 404
    if journey.status not in ("active", "paused", "sos"):
        return jsonify({"error": f"Journey is already {journey.status}."}), 400

    _set_status(journey, "ended")
    db.session.commit()
    return jsonify({"message": "Journey ended.", "journey": _journey_payload(journey)}), 200


@journeys_bp.post("/<int:journey_id>/cancel")
@jwt_required()
def cancel_journey(journey_id: int):
    """Cancel a journey without completing it."""
    journey = _owned_journey(journey_id, _user_id())
    if not journey:
        return jsonify({"error": "Journey not found."}), 404
    if journey.status not in ("active", "paused"):
        return jsonify({"error": f"Cannot cancel a journey that is {journey.status}."}), 400

    _set_status(journey, "cancelled")
    db.session.commit()
    return (
        jsonify({"message": "Journey cancelled.", "journey": _journey_payload(journey)}),
        200,
    )


@journeys_bp.post("/<int:journey_id>/sos")
@jwt_required()
def manual_sos(journey_id: int):
    """
    Manual SOS shell (Phase 5 / 10).
    Creates an SOS alert and marks the journey as sos.
    Trusted-contact notification is expanded in Phase 10–12.
    """
    user_id = _user_id()
    journey = _owned_journey(journey_id, user_id)
    if not journey:
        return jsonify({"error": "Journey not found."}), 404
    if journey.status not in ("active", "paused", "sos"):
        return jsonify({"error": f"Cannot trigger SOS on a {journey.status} journey."}), 400

    data = request.get_json(silent=True) or {}
    lat = _optional_float(data, "lat")
    lng = _optional_float(data, "lng")

    # Prefer provided coords, else last known location log
    if lat is None or lng is None:
        last = (
            LocationLog.query.filter_by(journey_id=journey.id)
            .order_by(LocationLog.recorded_at.desc())
            .first()
        )
        if last:
            lat = last.lat if lat is None else lat
            lng = last.lng if lng is None else lng

    alert = create_sos_alert(
        journey,
        sos_type="manual",
        reason=data.get("reason") or "Manual SOS button pressed",
        lat=lat,
        lng=lng,
    )
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Manual SOS triggered.",
                "sos": alert.to_dict(),
                "journey": _journey_payload(journey),
                "note": "Contact notification dashboard comes in Phase 10–12. Alert is stored.",
            }
        ),
        201,
    )


@journeys_bp.post("/<int:journey_id>/locations")
@jwt_required()
def post_location(journey_id: int):
    """
    Store a GPS location update for an active journey.
    Body: { lat, lng, accuracy?, speed?, heading?, recorded_at? }
    """
    user_id = _user_id()
    journey = _owned_journey(journey_id, user_id)
    if not journey:
        return jsonify({"error": "Journey not found."}), 404
    if journey.status != "active":
        return (
            jsonify({"error": "Locations can only be recorded for an active journey."}),
            400,
        )

    data = request.get_json(silent=True) or {}
    try:
        lat = float(data["lat"])
        lng = float(data["lng"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "lat and lng are required numbers."}), 400

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return jsonify({"error": "lat/lng out of valid range."}), 400

    log = LocationLog(
        journey_id=journey.id,
        lat=lat,
        lng=lng,
        accuracy=_optional_float(data, "accuracy"),
        speed=_optional_float(data, "speed"),
        heading=_optional_float(data, "heading"),
        recorded_at=_parse_iso_datetime(data.get("recorded_at")),
    )
    db.session.add(log)
    db.session.commit()

    # Phase 7 + 8: monitoring metrics then rule-based anomaly evaluation
    result = evaluate_anomalies(journey)

    return (
        jsonify(
            {
                "message": "Location saved.",
                "location": log.to_dict(),
                "interval_sec": current_app.config.get("LOCATION_INTERVAL_SEC", 5),
                "monitoring": result["monitoring"],
                "open_anomalies": result["open_anomalies"],
                "newly_created_anomalies": result["newly_created"],
                "active_safety_check": result["active_safety_check"],
            }
        ),
        201,
    )


@journeys_bp.get("/<int:journey_id>/monitoring")
@jwt_required()
def get_monitoring(journey_id: int):
    """
    Phase 7–8 – monitoring snapshot + open anomalies.
    """
    journey = _owned_journey(journey_id, _user_id())
    if not journey:
        return jsonify({"error": "Journey not found."}), 404
    result = evaluate_anomalies(journey)
    return (
        jsonify(
            {
                "monitoring": result["monitoring"],
                "open_anomalies": result["open_anomalies"],
                "newly_created_anomalies": result["newly_created"],
                "active_safety_check": result["active_safety_check"],
            }
        ),
        200,
    )


@journeys_bp.get("/<int:journey_id>/anomalies")
@jwt_required()
def list_anomalies(journey_id: int):
    """List anomalies for a journey (newest first)."""
    from app.models.anomaly import Anomaly

    journey = _owned_journey(journey_id, _user_id())
    if not journey:
        return jsonify({"error": "Journey not found."}), 404

    rows = (
        Anomaly.query.filter_by(journey_id=journey.id)
        .order_by(Anomaly.detected_at.desc())
        .all()
    )
    return jsonify({"anomalies": [a.to_dict() for a in rows]}), 200


@journeys_bp.post("/<int:journey_id>/demo/simulate-anomaly")
@jwt_required()
def demo_simulate_anomaly(journey_id: int):
    """
    Demo Mode only – simulate an anomaly for viva without waiting for real rules.
    Body: { type: prolonged_stop|route_deviation|lost_signal|speed_spike }
    """
    journey = _owned_journey(journey_id, _user_id())
    if not journey:
        return jsonify({"error": "Journey not found."}), 404
    if journey.status not in ("active", "paused"):
        return jsonify({"error": "Journey must be active or paused for demo."}), 400

    data = request.get_json(silent=True) or {}
    anomaly_type = (data.get("type") or "prolonged_stop").strip()
    try:
        result = simulate_anomaly(journey, anomaly_type)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result), 201


@journeys_bp.get("/<int:journey_id>/locations")
@jwt_required()
def list_locations(journey_id: int):
    """List stored GPS points for a journey (oldest first for path drawing)."""
    journey = _owned_journey(journey_id, _user_id())
    if not journey:
        return jsonify({"error": "Journey not found."}), 404

    limit = request.args.get("limit", default=200, type=int)
    limit = max(1, min(limit, 1000))

    logs = (
        LocationLog.query.filter_by(journey_id=journey.id)
        .order_by(LocationLog.recorded_at.asc())
        .limit(limit)
        .all()
    )
    return jsonify({"locations": [log.to_dict() for log in logs], "count": len(logs)}), 200
