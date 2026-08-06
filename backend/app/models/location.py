"""
Location log – GPS points collected during a journey (Phase 4+).
"""
from datetime import datetime, timezone
from app.extensions import db


class LocationLog(db.Model):
    __tablename__ = "location_logs"

    id = db.Column(db.Integer, primary_key=True)
    journey_id = db.Column(db.Integer, db.ForeignKey("journeys.id"), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float, nullable=True)
    speed = db.Column(db.Float, nullable=True)  # m/s if available
    heading = db.Column(db.Float, nullable=True)
    recorded_at = db.Column(db.DateTime, nullable=False)  # client timestamp
    received_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    journey = db.relationship("Journey", back_populates="location_logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "journey_id": self.journey_id,
            "lat": self.lat,
            "lng": self.lng,
            "accuracy": self.accuracy,
            "speed": self.speed,
            "heading": self.heading,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "received_at": self.received_at.isoformat() if self.received_at else None,
        }
