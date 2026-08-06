"""
Maps / safer-route / crime heatmap APIs (Phases 13–14 supporting modules).
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.services.crime_data import get_crime_meta, get_hotspots
from app.services.routing import fetch_safer_routes, geocode_search

maps_bp = Blueprint("maps", __name__)


@maps_bp.get("/crime-hotspots")
@jwt_required()
def crime_hotspots():
    """Crime points for heatmap (Kaggle Indian Crimes Dataset when available)."""
    rebuild = request.args.get("rebuild", "").lower() in ("1", "true", "yes")
    if rebuild:
        from app.services.crime_data import reload_crime_dataset

        reload_crime_dataset()

    hotspots = get_hotspots()
    meta = get_crime_meta()
    heat = [[h["lat"], h["lng"], float(h.get("intensity", 0.5))] for h in hotspots]
    return jsonify({"meta": meta, "hotspots": hotspots, "heat": heat}), 200


@maps_bp.get("/geocode")
@jwt_required()
def geocode():
    """Place search (Nominatim via backend)."""
    q = request.args.get("q", "")
    results = geocode_search(q, limit=int(request.args.get("limit", 5)))
    return jsonify({"results": results}), 200


@maps_bp.post("/safer-routes")
@jwt_required()
def safer_routes():
    """
    Body: { start_lat, start_lng, dest_lat, dest_lng }
    Returns ranked routes with Safety Score + geometry.
    """
    data = request.get_json(silent=True) or {}
    try:
        start_lat = float(data["start_lat"])
        start_lng = float(data["start_lng"])
        dest_lat = float(data["dest_lat"])
        dest_lng = float(data["dest_lng"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "start_lat, start_lng, dest_lat, dest_lng are required."}), 400

    result = fetch_safer_routes(start_lat, start_lng, dest_lat, dest_lng)
    if not result["routes"]:
        return jsonify(
            {
                "error": result.get("error")
                or "Could not compute street routes. Try again.",
            }
        ), 502
    return jsonify(result), 200
