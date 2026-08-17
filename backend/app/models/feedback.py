"""
Route safety user feedback model.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db


class RouteFeedback(db.Model):
    __tablename__ = "route_feedbacks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    journey_id = db.Column(db.Integer, db.ForeignKey("journeys.id"), nullable=True)
    dest_label = db.Column(db.String(255), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    rating = db.Column(db.Integer, nullable=False, default=3)  # 1 to 5 stars
    safety_tags = db.Column(db.String(255), nullable=True)  # comma-separated tags
    comments = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", backref=db.backref("feedbacks", lazy=True))
    journey = db.relationship("Journey", backref=db.backref("feedbacks", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else "Anonymous User",
            "journey_id": self.journey_id,
            "dest_label": self.dest_label,
            "lat": self.lat,
            "lng": self.lng,
            "rating": self.rating,
            "safety_tags": [t.strip() for t in (self.safety_tags or "").split(",") if t.strip()],
            "comments": self.comments,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
