"""
Safety verification – "Are you safe?" gate before SOS (Phase 9+).
"""
from datetime import datetime, timezone
from app.extensions import db


class SafetyCheck(db.Model):
    __tablename__ = "safety_checks"

    id = db.Column(db.Integer, primary_key=True)
    anomaly_id = db.Column(db.Integer, db.ForeignKey("anomalies.id"), nullable=False)
    journey_id = db.Column(db.Integer, db.ForeignKey("journeys.id"), nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default="pending"
    )  # pending|safe|need_help|timeout|cancelled
    prompted_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    responded_at = db.Column(db.DateTime, nullable=True)
    countdown_seconds = db.Column(db.Integer, nullable=True)
    response = db.Column(db.String(20), nullable=True)  # safe|need_help|null

    anomaly = db.relationship("Anomaly", back_populates="safety_checks")
    journey = db.relationship("Journey", back_populates="safety_checks")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "anomaly_id": self.anomaly_id,
            "journey_id": self.journey_id,
            "status": self.status,
            "prompted_at": self.prompted_at.isoformat() if self.prompted_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "countdown_seconds": self.countdown_seconds,
            "response": self.response,
        }
