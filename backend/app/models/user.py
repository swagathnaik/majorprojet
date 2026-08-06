"""
User model – registration, login, profile.
Passwords are stored as hashes only (Werkzeug).
"""
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships (used in later phases)
    emergency_contacts = db.relationship(
        "EmergencyContact", back_populates="user", cascade="all, delete-orphan"
    )
    journeys = db.relationship(
        "Journey", back_populates="user", cascade="all, delete-orphan"
    )
    sos_alerts = db.relationship(
        "SosAlert", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        """Hash and store the password. Never store plain text."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """Safe public representation (no password)."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.email}>"
