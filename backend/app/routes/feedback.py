"""
User feedback & AI model retraining routes.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.feedback_service import (
    get_feedback_stats,
    retrain_model,
    submit_feedback,
)
from app.models.feedback import RouteFeedback

feedback_bp = Blueprint("feedback", __name__)


def _current_user_id() -> int | None:
    try:
        ident = get_jwt_identity()
        return int(ident) if ident else None
    except Exception:
        return None


@feedback_bp.post("")
def create_feedback():
    """
    Submit user safety feedback for a route or location.
    Body: {
      journey_id?, dest_label?, lat?, lng?,
      rating (1-5), safety_tags (list/string), comments?
    }
    """
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    try:
        rating = int(rating)
        rating = max(1, min(5, rating))
    except (TypeError, ValueError):
        rating = 3

    user_id = _current_user_id()
    feedback = submit_feedback(
        user_id=user_id,
        journey_id=data.get("journey_id"),
        dest_label=data.get("dest_label"),
        lat=data.get("lat"),
        lng=data.get("lng"),
        rating=rating,
        safety_tags=data.get("safety_tags"),
        comments=data.get("comments"),
    )

    stats = get_feedback_stats()
    return (
        jsonify(
            {
                "message": "Feedback submitted and AI safety model updated successfully.",
                "feedback": feedback.to_dict(),
                "stats": stats,
            }
        ),
        201,
    )


@feedback_bp.get("")
def list_feedback():
    """Get recent feedback submissions and aggregate stats."""
    feedbacks = (
        RouteFeedback.query.order_by(RouteFeedback.created_at.desc()).limit(50).all()
    )
    stats = get_feedback_stats()
    return jsonify(
        {
            "feedbacks": [f.to_dict() for f in feedbacks],
            "stats": stats,
        }
    )


@feedback_bp.post("/retrain")
def retrain_route_safety_model():
    """
    Explicitly trigger AI Model Retraining using all submitted user feedback.
    Returns retraining performance metrics & updated model weights.
    """
    retrain_metrics = retrain_model()
    stats = get_feedback_stats()
    return jsonify(
        {
            "message": "AI Safety Model successfully retrained on community user feedback.",
            "metrics": retrain_metrics,
            "stats": stats,
        }
    )
