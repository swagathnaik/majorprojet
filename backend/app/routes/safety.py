"""
Safety check routes – Phase 9 "Are you safe?" verification.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.journey import Journey
from app.models.safety_check import SafetyCheck
from app.models.contact import EmergencyContact
from app.services.safety_verification import (
    cancel_countdown,
    respond_to_safety_check,
    safety_check_payload,
    timeout_safety_check,
)

safety_bp = Blueprint("safety", __name__)


def _user_id() -> int:
    return int(get_jwt_identity())


def _optional_float(data, key):
    if data.get(key) is None or data.get(key) == "":
        return None
    try:
        return float(data[key])
    except (TypeError, ValueError):
        return None


def _owned_check(check_id: int, user_id: int) -> tuple[SafetyCheck | None, Journey | None]:
    check = db.session.get(SafetyCheck, check_id)
    if not check:
        return None, None
    journey = Journey.query.filter_by(id=check.journey_id, user_id=user_id).first()
    if not journey:
        return None, None
    return check, journey


def _journey_payload(journey: Journey) -> dict:
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
    return payload


@safety_bp.get("/<int:check_id>")
@jwt_required()
def get_safety_check(check_id: int):
    check, journey = _owned_check(check_id, _user_id())
    if not check:
        return jsonify({"error": "Safety check not found."}), 404
    return jsonify({"safety_check": safety_check_payload(check)}), 200


@safety_bp.post("/<int:check_id>/respond")
@jwt_required()
def respond(check_id: int):
    """
    Body: { response: "safe" | "need_help", lat?, lng? }
    """
    check, journey = _owned_check(check_id, _user_id())
    if not check:
        return jsonify({"error": "Safety check not found."}), 404

    data = request.get_json(silent=True) or {}
    try:
        result = respond_to_safety_check(
            check,
            journey,
            data.get("response"),
            lat=_optional_float(data, "lat"),
            lng=_optional_float(data, "lng"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    result["journey"] = _journey_payload(journey)
    return jsonify(result), 200


@safety_bp.post("/<int:check_id>/cancel-countdown")
@jwt_required()
def cancel(check_id: int):
    """Cancel false-alarm countdown → mark safe."""
    check, journey = _owned_check(check_id, _user_id())
    if not check:
        return jsonify({"error": "Safety check not found."}), 404
    try:
        result = cancel_countdown(check, journey)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    result["journey"] = _journey_payload(journey)
    return jsonify(result), 200


@safety_bp.post("/<int:check_id>/timeout")
@jwt_required()
def timeout(check_id: int):
    """
    Called when UI countdown reaches 0 with no response → automatic SOS.
    Body: { lat?, lng? }
    """
    check, journey = _owned_check(check_id, _user_id())
    if not check:
        return jsonify({"error": "Safety check not found."}), 404

    data = request.get_json(silent=True) or {}
    try:
        result = timeout_safety_check(
            check,
            journey,
            lat=_optional_float(data, "lat"),
            lng=_optional_float(data, "lng"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    result["journey"] = _journey_payload(journey)
    return jsonify(result), 200
