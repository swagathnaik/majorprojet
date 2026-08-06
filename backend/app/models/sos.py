"""
SOS alert – manual or automatic escalation (Phase 10–11).
"""
from datetime import datetime, timezone
from app.extensions import db


class SosAlert(db.Model):
    __tablename__ = "sos_alerts"

    id = db.Column(db.Integer, primary_key=True)
    journey_id = db.Column(db.Integer, db.ForeignKey("journeys.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # manual|automatic
    trigger_reason = db.Column(db.String(255), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    status = db.Column(
        db.String(20), nullable=False, default="active"
    )  # active|resolved|cancelled
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at = db.Column(db.DateTime, nullable=True)

    journey = db.relationship("Journey", back_populates="sos_alerts")
    user = db.relationship("User", back_populates="sos_alerts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "journey_id": self.journey_id,
            "user_id": self.user_id,
            "type": self.type,
            "trigger_reason": self.trigger_reason,
            "lat": self.lat,
            "lng": self.lng,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
