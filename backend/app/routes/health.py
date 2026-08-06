"""Health check – verifies the API is running (Phase 1 smoke test)."""
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "SafeRoute API"}), 200
