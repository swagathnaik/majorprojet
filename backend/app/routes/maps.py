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
@jwt_required(optional=True)
def geocode():
    """Place search (Nominatim / Mapbox via backend)."""
    q = request.args.get("q", "")
    results = geocode_search(q, limit=int(request.args.get("limit", 5)))
    return jsonify({"results": results}), 200


@maps_bp.get("/reverse-geocode")
@jwt_required(optional=True)
def reverse_geocode_route():
    """Convert lat,lng to human-readable address label."""
    from app.services.routing import reverse_geocode as rev_geo
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid lat and lng query params are required"}), 400
    res = rev_geo(lat, lng)
    return jsonify(res), 200


@maps_bp.get("/ip-location")
@jwt_required(optional=True)
def ip_location_route():
    """Get approximate location based on client IP or network fallback."""
    from app.services.routing import get_ip_location as ip_loc
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    res = ip_loc(client_ip)
    return jsonify(res), 200


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


@maps_bp.get("/police-stations")
@jwt_required(optional=True)
def police_stations_route():
    """
    List verified police stations, optionally sorted by distance to user lat/lng.
    Query params: lat (float), lng (float), radius_km (float)
    """
    from app.services.police_data import get_all_police_stations

    user_lat = request.args.get("lat", type=float)
    user_lng = request.args.get("lng", type=float)
    radius_km = request.args.get("radius_km", type=float)

    stations = get_all_police_stations(
        user_lat=user_lat, user_lng=user_lng, max_radius_km=radius_km
    )
    return jsonify({"success": True, "count": len(stations), "police_stations": stations}), 200


@maps_bp.get("/nearest-police-station")
@jwt_required(optional=True)
def nearest_police_station_route():
    """
    Find the closest police station to given coordinates with full details and distance.
    Query params: lat (float, required), lng (float, required)
    """
    from app.services.police_data import get_nearest_police_station

    user_lat = request.args.get("lat", type=float)
    user_lng = request.args.get("lng", type=float)

    if user_lat is None or user_lng is None:
        return jsonify({"error": "Both 'lat' and 'lng' query parameters are required"}), 400

    station = get_nearest_police_station(user_lat, user_lng)
    if not station:
        return jsonify({"error": "No police station found"}), 404

    return jsonify({"success": True, "nearest_station": station}), 200

