"""
Journey model – Safe Journey Mode (Phase 5+).
"""
from datetime import datetime, timezone
import secrets
from app.extensions import db


class Journey(db.Model):
    __tablename__ = "journeys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="planned",
    )  # planned|active|paused|ended|cancelled|sos

    start_lat = db.Column(db.Float, nullable=True)
    start_lng = db.Column(db.Float, nullable=True)
    dest_lat = db.Column(db.Float, nullable=True)
    dest_lng = db.Column(db.Float, nullable=True)
    dest_label = db.Column(db.String(255), nullable=True)

    expected_route_json = db.Column(db.Text, nullable=True)
    share_token = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        default=lambda: secrets.token_urlsafe(32),
    )
    active_contact_id = db.Column(
        db.Integer, db.ForeignKey("emergency_contacts.id"), nullable=True
    )

    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="journeys")
    location_logs = db.relationship(
        "LocationLog", back_populates="journey", cascade="all, delete-orphan"
    )
    anomalies = db.relationship(
        "Anomaly", back_populates="journey", cascade="all, delete-orphan"
    )
    safety_checks = db.relationship(
        "SafetyCheck", back_populates="journey", cascade="all, delete-orphan"
    )
    sos_alerts = db.relationship(
        "SosAlert", back_populates="journey", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        route = None
        if self.expected_route_json:
            import json

            try:
                route = json.loads(self.expected_route_json)
            except (TypeError, ValueError):
                route = None
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "start_lat": self.start_lat,
            "start_lng": self.start_lng,
            "dest_lat": self.dest_lat,
            "dest_lng": self.dest_lng,
            "dest_label": self.dest_label,
            "expected_route": route,
            "share_token": self.share_token,
            "active_contact_id": self.active_contact_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
