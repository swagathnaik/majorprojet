"""
Anomaly model – potential unusual journey patterns (Phase 8+).
Does NOT claim crime/attack detection.
"""
from datetime import datetime, timezone
import json
from app.extensions import db


class Anomaly(db.Model):
    __tablename__ = "anomalies"

    id = db.Column(db.Integer, primary_key=True)
    journey_id = db.Column(db.Integer, db.ForeignKey("journeys.id"), nullable=False)
    type = db.Column(
        db.String(50), nullable=False
    )  # prolonged_stop|route_deviation|lost_signal|speed_spike
    severity = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(
        db.String(20), nullable=False, default="open"
    )  # open|cleared|escalated
    details_json = db.Column(db.Text, nullable=True)
    detected_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    cleared_at = db.Column(db.DateTime, nullable=True)

    journey = db.relationship("Journey", back_populates="anomalies")
    safety_checks = db.relationship(
        "SafetyCheck", back_populates="anomaly", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        details = None
        if self.details_json:
            try:
                details = json.loads(self.details_json)
            except (TypeError, ValueError):
                details = {"raw": self.details_json}
        return {
            "id": self.id,
            "journey_id": self.journey_id,
            "type": self.type,
            "severity": self.severity,
            "status": self.status,
            "details": details,
            "details_json": self.details_json,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "cleared_at": self.cleared_at.isoformat() if self.cleared_at else None,
        }
