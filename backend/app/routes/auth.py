"""
Authentication routes – register, login, current user profile.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from email_validator import validate_email, EmailNotValidError

from app.extensions import db
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


def _validate_password(password: str) -> str | None:
    """Return an error message if password is weak, else None."""
    if not password or len(password) < 6:
        return "Password must be at least 6 characters."
    return None


@auth_bp.post("/register")
def register():
    """
    Create a new user account.
    Body JSON: { name, email, phone?, password }
    """
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip() or None
    password = data.get("password") or ""

    if not name:
        return jsonify({"error": "Name is required."}), 400
    if not email:
        return jsonify({"error": "Email is required."}), 400

    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        return jsonify({"error": "Invalid email address."}), 400

    password_error = _validate_password(password)
    if password_error:
        return jsonify({"error": password_error}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email is already registered."}), 409

    user = User(name=name, email=email, phone=phone)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))

    return (
        jsonify(
            {
                "message": "Registration successful.",
                "access_token": access_token,
                "user": user.to_dict(),
            }
        ),
        201,
    )


@auth_bp.post("/login")
def login():
    """
    Log in with email + password.
    Body JSON: { email, password }
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401

    access_token = create_access_token(identity=str(user.id))

    return jsonify(
        {
            "message": "Login successful.",
            "access_token": access_token,
            "user": user.to_dict(),
        }
    ), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    """Return the currently authenticated user's profile."""
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"user": user.to_dict()}), 200


@auth_bp.put("/me")
@jwt_required()
def update_me():
    """
    Update basic profile fields.
    Body JSON: { name?, phone? }
    """
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Name cannot be empty."}), 400
        user.name = name

    if "phone" in data:
        phone = (data.get("phone") or "").strip()
        user.phone = phone or None

    db.session.commit()
    return jsonify({"message": "Profile updated.", "user": user.to_dict()}), 200
