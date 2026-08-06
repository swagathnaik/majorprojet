"""
Emergency contact model (Phase 3 will add full CRUD routes).
Schema is created now so migrations stay consistent.
"""
from datetime import datetime, timezone
import secrets
from app.extensions import db


class EmergencyContact(db.Model):
    __tablename__ = "emergency_contacts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    relationship = db.Column(db.String(50), nullable=True)  # Mother, Friend, etc.
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    # Opaque token for trusted-contact dashboard link (no full login needed)
    share_token = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        default=lambda: secrets.token_urlsafe(32),
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="emergency_contacts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "phone": self.phone,
            "relationship": self.relationship,
            "is_primary": self.is_primary,
            "share_token": self.share_token,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
