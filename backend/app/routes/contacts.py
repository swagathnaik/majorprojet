"""
Emergency contact management – add, list, edit, delete, set primary.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.contact import EmergencyContact

contacts_bp = Blueprint("contacts", __name__)

RELATIONSHIP_CHOICES = {
    "Mother",
    "Father",
    "Sibling",
    "Friend",
    "Spouse",
    "Guardian",
    "Other",
}


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _get_owned_contact(contact_id: int, user_id: int):
    """Return contact if it belongs to the user, else None."""
    return EmergencyContact.query.filter_by(id=contact_id, user_id=user_id).first()


def _clear_other_primaries(user_id: int, except_id: int | None = None) -> None:
    """Ensure only one primary contact per user."""
    query = EmergencyContact.query.filter_by(user_id=user_id, is_primary=True)
    if except_id is not None:
        query = query.filter(EmergencyContact.id != except_id)
    for contact in query.all():
        contact.is_primary = False


def _validate_payload(data: dict, *, partial: bool = False) -> tuple[dict | None, str | None]:
    """
    Validate create/update payload.
    Returns (cleaned_fields, error_message).
    """
    cleaned = {}

    if "name" in data or not partial:
        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required."
        if len(name) > 120:
            return None, "Name is too long."
        cleaned["name"] = name

    if "phone" in data or not partial:
        phone = (data.get("phone") or "").strip()
        if not phone:
            return None, "Phone number is required."
        # Keep digits, +, spaces, dashes – basic academic validation
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) < 7 or len(digits) > 15:
            return None, "Phone number looks invalid."
        if len(phone) > 20:
            return None, "Phone number is too long."
        cleaned["phone"] = phone

    if "relationship" in data or not partial:
        relationship = (data.get("relationship") or "").strip() or None
        if relationship and relationship not in RELATIONSHIP_CHOICES:
            return None, f"Relationship must be one of: {', '.join(sorted(RELATIONSHIP_CHOICES))}."
        cleaned["relationship"] = relationship

    if "is_primary" in data:
        cleaned["is_primary"] = bool(data.get("is_primary"))

    return cleaned, None


@contacts_bp.get("")
@jwt_required()
def list_contacts():
    """List all emergency contacts for the logged-in user."""
    user_id = _current_user_id()
    contacts = (
        EmergencyContact.query.filter_by(user_id=user_id)
        .order_by(EmergencyContact.is_primary.desc(), EmergencyContact.created_at.asc())
        .all()
    )
    return jsonify({"contacts": [c.to_dict() for c in contacts]}), 200


@contacts_bp.post("")
@jwt_required()
def create_contact():
    """
    Add an emergency contact.
    Body: { name, phone, relationship?, is_primary? }
    """
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}
    cleaned, error = _validate_payload(data, partial=False)
    if error:
        return jsonify({"error": error}), 400

    make_primary = cleaned.pop("is_primary", False)
    # First contact automatically becomes primary
    existing_count = EmergencyContact.query.filter_by(user_id=user_id).count()
    if existing_count == 0:
        make_primary = True

    if make_primary:
        _clear_other_primaries(user_id)

    contact = EmergencyContact(
        user_id=user_id,
        name=cleaned["name"],
        phone=cleaned["phone"],
        relationship=cleaned.get("relationship"),
        is_primary=make_primary,
    )
    db.session.add(contact)
    db.session.commit()

    return (
        jsonify({"message": "Emergency contact added.", "contact": contact.to_dict()}),
        201,
    )


@contacts_bp.get("/<int:contact_id>")
@jwt_required()
def get_contact(contact_id: int):
    """Get a single contact owned by the user."""
    user_id = _current_user_id()
    contact = _get_owned_contact(contact_id, user_id)
    if not contact:
        return jsonify({"error": "Contact not found."}), 404
    return jsonify({"contact": contact.to_dict()}), 200


@contacts_bp.put("/<int:contact_id>")
@jwt_required()
def update_contact(contact_id: int):
    """
    Edit an emergency contact.
    Body: { name?, phone?, relationship?, is_primary? }
    """
    user_id = _current_user_id()
    contact = _get_owned_contact(contact_id, user_id)
    if not contact:
        return jsonify({"error": "Contact not found."}), 404

    data = request.get_json(silent=True) or {}
    cleaned, error = _validate_payload(data, partial=True)
    if error:
        return jsonify({"error": error}), 400
    if not cleaned:
        return jsonify({"error": "No fields to update."}), 400

    if cleaned.get("is_primary"):
        _clear_other_primaries(user_id, except_id=contact.id)

    for key, value in cleaned.items():
        setattr(contact, key, value)

    db.session.commit()
    return jsonify({"message": "Contact updated.", "contact": contact.to_dict()}), 200


@contacts_bp.patch("/<int:contact_id>/primary")
@jwt_required()
def set_primary(contact_id: int):
    """Mark this contact as the primary emergency contact."""
    user_id = _current_user_id()
    contact = _get_owned_contact(contact_id, user_id)
    if not contact:
        return jsonify({"error": "Contact not found."}), 404

    _clear_other_primaries(user_id, except_id=contact.id)
    contact.is_primary = True
    db.session.commit()

    return (
        jsonify({"message": "Primary contact updated.", "contact": contact.to_dict()}),
        200,
    )


@contacts_bp.delete("/<int:contact_id>")
@jwt_required()
def delete_contact(contact_id: int):
    """Delete an emergency contact. If primary is deleted, promote another."""
    user_id = _current_user_id()
    contact = _get_owned_contact(contact_id, user_id)
    if not contact:
        return jsonify({"error": "Contact not found."}), 404

    was_primary = contact.is_primary
    db.session.delete(contact)
    db.session.flush()

    if was_primary:
        replacement = (
            EmergencyContact.query.filter_by(user_id=user_id)
            .order_by(EmergencyContact.created_at.asc())
            .first()
        )
        if replacement:
            replacement.is_primary = True

    db.session.commit()
    return jsonify({"message": "Contact deleted."}), 200
