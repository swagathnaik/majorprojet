"""
Geocoding (Nominatim) + road routing (OSRM) with safer-path ranking.
Returns real street-following geometry (Google Maps–style), not straight lines.
"""
from __future__ import annotations

import json
import math
import ssl
import urllib.error
import urllib.parse
import urllib.request

from app.services.crime_data import score_route_lnglat
from app.utils.geo import haversine_m

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_BASE = "https://router.project-osrm.org/route/v1"
USER_AGENT = "SafeRouteAcademicDemo/1.0 (student project)"

# Prefer driving for Google Maps–like street paths; foot as backup profile.
OSRM_PROFILES = ("driving", "foot")


GEOCODE_CACHE: dict[str, list[dict]] = {}

PRESET_LOCATIONS: list[dict] = [
    {
        "label": "Acharya Institutes, Soladevanahalli, Hesaraghatta Main Rd, Bengaluru",
        "lat": 13.0837,
        "lng": 77.4857,
        "type": "education",
        "keywords": ["acharya", "acharya institute", "soladevanahalli", "acharya college", "soladevanahali", "acharyainstitutes"],
    },
    {
        "label": "Soladevanahalli, Yelahanka Hobli, Bengaluru Urban, Karnataka",
        "lat": 13.0868,
        "lng": 77.4876,
        "type": "suburb",
        "keywords": ["soladevanahalli", "soladevanahali", "soladevanahallii", "solad"],
    },
    {
        "label": "Acharya Lake, Soladevanahalli, Bengaluru",
        "lat": 13.0850,
        "lng": 77.4830,
        "type": "water",
        "keywords": ["acharya lake", "acharya water", "hesaraghatta lake"],
    },
    {
        "label": "Chikkabanavara Railway Station, Bengaluru",
        "lat": 13.0760,
        "lng": 77.5090,
        "type": "station",
        "keywords": ["chikkabanavara", "chikkabanavara station"],
    },
    {
        "label": "Yelahanka New Town, Bengaluru, Karnataka",
        "lat": 13.0995,
        "lng": 77.5925,
        "type": "suburb",
        "keywords": ["yelahanka", "yelahanka new town", "yelahanka station"],
    },
    {
        "label": "IISc (Indian Institute of Science), Malleshwaram, Bengaluru",
        "lat": 13.0184,
        "lng": 77.5682,
        "type": "education",
        "keywords": ["iisc", "indian institute of science", "malleshwaram"],
    },
    {
        "label": "KSR Bengaluru City Railway Station (Majestic), Bengaluru",
        "lat": 12.9781,
        "lng": 77.5697,
        "type": "station",
        "keywords": ["majestic", "ksr bengaluru", "railway station", "bangalore station"],
    },
    {
        "label": "MG Road Metro Station, Mahatma Gandhi Rd, Bengaluru",
        "lat": 12.9756,
        "lng": 77.6066,
        "type": "station",
        "keywords": ["mg road", "brigade road", "mg road metro"],
    },
    {
        "label": "Indiranagar 100 Feet Road, Bengaluru",
        "lat": 12.9784,
        "lng": 77.6408,
        "type": "suburb",
        "keywords": ["indiranagar", "100ft road"],
    },
    {
        "label": "Koramangala 5th Block, Bengaluru",
        "lat": 12.9352,
        "lng": 77.6245,
        "type": "suburb",
        "keywords": ["koramangala", "koramangala 5th block"],
    },
    {
        "label": "ITPL (International Tech Park), Whitefield, Bengaluru",
        "lat": 12.9863,
        "lng": 77.7381,
        "type": "commercial",
        "keywords": ["whitefield", "itpl", "tech park"],
    },
    {
        "label": "Electronic City Phase 1, Bengaluru",
        "lat": 12.8452,
        "lng": 77.6602,
        "type": "suburb",
        "keywords": ["electronic city", "e-city", "ecity"],
    },
    {
        "label": "Kempegowda International Airport (BLR), Devanahalli, Bengaluru",
        "lat": 13.1986,
        "lng": 77.7066,
        "type": "airport",
        "keywords": ["airport", "blr airport", "kempegowda airport", "devanahalli"],
    },
    {
        "label": "Hebbal Flyover / Lake, Bengaluru",
        "lat": 13.0358,
        "lng": 77.5970,
        "type": "suburb",
        "keywords": ["hebbal", "hebbal flyover", "hebbal lake"],
    },
    {
        "label": "Rajajinagar, Bengaluru",
        "lat": 12.9982,
        "lng": 77.5530,
        "type": "suburb",
        "keywords": ["rajajinagar"],
    },
    {
        "label": "Jayanagar 4th Block, Bengaluru",
        "lat": 12.9299,
        "lng": 77.5824,
        "type": "suburb",
        "keywords": ["jayanagar"],
    },
    {
        "label": "BTM Layout 2nd Stage, Bengaluru",
        "lat": 12.9166,
        "lng": 77.6101,
        "type": "suburb",
        "keywords": ["btm", "btm layout"],
    },
    {
        "label": "HSR Layout, Bengaluru",
        "lat": 12.9121,
        "lng": 77.6446,
        "type": "suburb",
        "keywords": ["hsr", "hsr layout"],
    },
    {
        "label": "Marathahalli Bridge, Outer Ring Rd, Bengaluru",
        "lat": 12.9592,
        "lng": 77.6974,
        "type": "suburb",
        "keywords": ["marathahalli"],
    },
    {
        "label": "Mysore Palace, Sayyaji Rao Rd, Mysuru, Karnataka",
        "lat": 12.3052,
        "lng": 76.6552,
        "type": "tourism",
        "keywords": ["mysore", "mysuru", "mysore palace"],
    },
]


def geocode_search(query: str, limit: int = 5) -> list[dict]:
    """Search places via local preset database + Nominatim with caching."""
    q = (query or "").strip().lower()
    if not q or len(q) < 2:
        return []

    # Check local preset landmarks first for instant 0ms response
    preset_matches: list[dict] = []
    seen_labels = set()

    for item in PRESET_LOCATIONS:
        # Match label substring or any keyword
        label_lower = item["label"].lower()
        keywords = item.get("keywords", [])
        if q in label_lower or any(q in kw for kw in keywords):
            entry = {
                "label": item["label"],
                "lat": item["lat"],
                "lng": item["lng"],
                "type": item.get("type", "location"),
            }
            if entry["label"] not in seen_labels:
                preset_matches.append(entry)
                seen_labels.add(entry["label"])

    # Check in-memory cache
    cache_key = q
    if cache_key in GEOCODE_CACHE:
        cached = GEOCODE_CACHE[cache_key]
        combined = list(preset_matches)
        for c in cached:
            if c["label"] not in seen_labels:
                combined.append(c)
                seen_labels.add(c["label"])
        return combined[:limit]

    # Attempt 1: Regional search with expanded Bangalore/KA viewbox
    params = urllib.parse.urlencode(
        {
            "q": q,
            "format": "json",
            "addressdetails": 1,
            "limit": max(1, min(limit, 8)),
            "countrycodes": "in",
            "viewbox": "77.10,13.45,78.15,12.45",
            "bounded": 0,
        }
    )
    rows = _http_get_json(f"{NOMINATIM_URL}?{params}", timeout=8) or []

    # Attempt 2: Fallback without viewbox (search anywhere in India)
    if not isinstance(rows, list) or len(rows) == 0:
        query_in = q if ("india" in q or "karnataka" in q or "bangalore" in q) else f"{q}, India"
        params_in = urllib.parse.urlencode(
            {
                "q": query_in,
                "format": "json",
                "addressdetails": 1,
                "limit": max(1, min(limit, 8)),
                "countrycodes": "in",
            }
        )
        rows = _http_get_json(f"{NOMINATIM_URL}?{params_in}", timeout=8) or []

    # Attempt 3: Global search fallback
    if not isinstance(rows, list) or len(rows) == 0:
        params_global = urllib.parse.urlencode(
            {
                "q": q,
                "format": "json",
                "addressdetails": 1,
                "limit": max(1, min(limit, 8)),
            }
        )
        rows = _http_get_json(f"{NOMINATIM_URL}?{params_global}", timeout=8) or []

    api_results = []
    if isinstance(rows, list):
        for row in rows:
            try:
                label = row.get("display_name")
                if label:
                    api_results.append(
                        {
                            "label": label,
                            "lat": float(row["lat"]),
                            "lng": float(row["lon"]),
                            "type": row.get("type"),
                        }
                    )
            except (KeyError, TypeError, ValueError):
                continue

    GEOCODE_CACHE[cache_key] = api_results

    combined = list(preset_matches)
    for c in api_results:
        if c["label"] not in seen_labels:
            combined.append(c)
            seen_labels.add(c["label"])

    return combined[:limit]


def fetch_safer_routes(
    start_lat: float,
    start_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> dict:
    """
    Fetch real road-following routes via OSRM, score each against crime data,
    rank by Safety Score (higher = safer).
    """
    routes = _collect_road_routes(start_lat, start_lng, dest_lat, dest_lng)
    if not routes:
        # Last resort: still try one more OSRM call with looser options
        routes = _osrm_route_points(
            [(start_lng, start_lat), (dest_lng, dest_lat)],
            profile="driving",
            alternatives=True,
            label_prefix="Route",
        )

    if not routes:
        return {
            "routes": [],
            "recommended_route_id": None,
            "error": "Could not reach road routing service. Check network / SSL.",
            "disclaimer": (
                "Unable to compute street paths right now. "
                "Try again in a moment."
            ),
        }

    # Deduplicate near-identical geometries but keep 2–4 options
    routes = _dedupe_routes(routes, min_unique_ratio=0.06)

    scored = []
    for idx, route in enumerate(routes):
        coords = route["coordinates"]  # [[lng,lat],...]
        metrics = score_route_lnglat(coords)
        scored.append(
            {
                "id": idx,
                "label": route.get("label") or f"Route {idx + 1}",
                "distance_m": route.get("distance_m") or metrics["distance_m"],
                "duration_sec": route.get("duration_sec"),
                "coordinates": coords,
                "geometry_latlng": [[c[1], c[0]] for c in coords],
                "safety_score": metrics["safety_score"],
                "risk_indicator": metrics["risk_indicator"],
                "crime_exposure": metrics["crime_exposure"],
                "note": metrics["note"],
                "source": route.get("source", "osrm"),
            }
        )

    scored.sort(key=lambda r: (-r["safety_score"], r["distance_m"] or 0))
    for i, r in enumerate(scored):
        r["rank"] = i + 1
        r["is_recommended"] = i == 0
        if i == 0:
            r["label"] = _with_safest_label(r["label"])

    return {
        "routes": scored,
        "recommended_route_id": scored[0]["id"] if scored else None,
        "disclaimer": (
            "Street paths from OpenStreetMap (OSRM), ranked by demo Safety Score. "
            "Not a guarantee of safety — does not replace local judgment or 112."
        ),
    }


def _collect_road_routes(start_lat, start_lng, dest_lat, dest_lng) -> list[dict]:
    """Build at least 2 real road paths when possible."""
    collected: list[dict] = []
    profile_used = "driving"

    for profile in OSRM_PROFILES:
        main = _osrm_route_points(
            [(start_lng, start_lat), (dest_lng, dest_lat)],
            profile=profile,
            alternatives=True,
            label_prefix="Fastest" if profile == "driving" else "Walking",
        )
        if main:
            collected.extend(main)
            profile_used = profile
            break

    if not collected:
        return []

    # Always request via-point alternatives so users see 2+ street options
    vias = _alternate_waypoints(start_lat, start_lng, dest_lat, dest_lng)
    for i, (via_lng, via_lat) in enumerate(vias[:4]):
        alt = _osrm_route_points(
            [(start_lng, start_lat), (via_lng, via_lat), (dest_lng, dest_lat)],
            profile=profile_used,
            alternatives=False,
            label_prefix=f"Alternative {i + 1}",
        )
        collected.extend(alt)
        if len(_dedupe_routes(collected, min_unique_ratio=0.06)) >= 3:
            break

    # If still only one path (very short trip), try the other profile
    if len(_dedupe_routes(collected, min_unique_ratio=0.08)) < 2:
        other = "foot" if profile_used == "driving" else "driving"
        extra = _osrm_route_points(
            [(start_lng, start_lat), (dest_lng, dest_lat)],
            profile=other,
            alternatives=True,
            label_prefix="Alt path",
        )
        collected.extend(extra)
        for i, (via_lng, via_lat) in enumerate(vias[:2]):
            collected.extend(
                _osrm_route_points(
                    [(start_lng, start_lat), (via_lng, via_lat), (dest_lng, dest_lat)],
                    profile=other,
                    alternatives=False,
                    label_prefix=f"Alt via {i + 1}",
                )
            )

    return collected


def _alternate_waypoints(
    start_lat: float,
    start_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> list[tuple[float, float]]:
    """
    Midpoints offset left/right (and farther offsets) so OSRM returns
    different street paths. Always returns at least two vias when distance allows.
    """
    dist = haversine_m(start_lat, start_lng, dest_lat, dest_lng)
    if dist < 120:
        # Tiny trips: still nudge slightly for a second path attempt
        return [
            (start_lng + 0.003, start_lat + 0.002),
            (start_lng - 0.003, start_lat - 0.002),
        ]

    mid_lat = (start_lat + dest_lat) / 2.0
    mid_lng = (start_lng + dest_lng) / 2.0
    dlat = dest_lat - start_lat
    dlng = dest_lng - start_lng
    length = math.hypot(dlat, dlng) or 1e-9
    ux, uy = -dlng / length, dlat / length

    m_per_deg_lat = 111_320.0
    m_per_deg_lng = 111_320.0 * max(0.2, math.cos(math.radians(mid_lat)))

    vias: list[tuple[float, float]] = []
    for frac in (0.07, 0.14):
        offset_m = min(1200.0, max(150.0, dist * frac))
        ox = (offset_m / m_per_deg_lng) * ux
        oy = (offset_m / m_per_deg_lat) * uy
        vias.append((mid_lng + ox, mid_lat + oy))
        vias.append((mid_lng - ox, mid_lat - oy))

    # Also offset at 1/3 and 2/3 along the corridor for more distinct roads
    for t in (0.33, 0.66):
        lat = start_lat + dlat * t
        lng = start_lng + dlng * t
        offset_m = min(900.0, max(160.0, dist * 0.09))
        ox = (offset_m / m_per_deg_lng) * ux
        oy = (offset_m / m_per_deg_lat) * uy
        vias.append((lng + ox, lat + oy))
        vias.append((lng - ox, lat - oy))

    return vias[:6]


def _osrm_route_points(
    points: list[tuple[float, float]],
    profile: str = "driving",
    alternatives: bool = False,
    label_prefix: str = "Route",
) -> list[dict]:
    """points: list of (lng, lat) — real road geometry from OSRM."""
    if len(points) < 2:
        return []

    coords = ";".join(f"{lng},{lat}" for lng, lat in points)
    alt_flag = "true" if alternatives else "false"
    url = (
        f"{OSRM_BASE}/{profile}/{coords}"
        f"?overview=full&geometries=geojson&alternatives={alt_flag}&steps=false"
        f"&continue_straight=false"
    )
    data = _http_get_json(url, timeout=20)
    if not data or data.get("code") != "Ok":
        return []

    routes = []
    for i, r in enumerate(data.get("routes") or []):
        geometry = r.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        if len(coordinates) < 3 and haversine_m(
            points[0][1], points[0][0], points[-1][1], points[-1][0]
        ) > 400:
            continue
        label = label_prefix if i == 0 else f"{label_prefix} #{i + 1}"
        routes.append(
            {
                "label": label,
                "distance_m": round(float(r.get("distance", 0)), 1),
                "duration_sec": int(r.get("duration", 0)),
                "coordinates": coordinates,
                "source": "osrm",
                "profile": profile,
            }
        )
    return routes


def _dedupe_routes(routes: list[dict], min_unique_ratio: float = 0.06) -> list[dict]:
    """Drop near-identical paths; keep up to 4 distinct street options."""
    kept: list[dict] = []
    for route in routes:
        coords = route["coordinates"]
        if not coords or len(coords) < 2:
            continue
        if not kept:
            kept.append(route)
            continue
        if any(_similar_path(coords, k["coordinates"]) for k in kept):
            continue
        kept.append(route)
        if len(kept) >= 4:
            break
    if len(kept) < 2 and len(routes) > 1:
        base = kept[0]["coordinates"] if kept else routes[0]["coordinates"]
        best = None
        best_score = -1.0
        for route in routes[1:]:
            if any(route is k for k in kept):
                continue
            samples = 10
            total = 0.0
            for i in range(samples):
                t = i / (samples - 1)
                pa = _point_at(base, t)
                pb = _point_at(route["coordinates"], t)
                total += haversine_m(pa[1], pa[0], pb[1], pb[0])
            if total > best_score:
                best_score = total
                best = route
        if best is not None:
            kept.append(best)
    return kept


def _similar_path(a: list, b: list) -> bool:
    """True only when paths nearly overlap (same street corridor)."""
    if not a or not b:
        return False
    samples = 12
    total = 0.0
    max_d = 0.0
    for i in range(samples):
        t = i / (samples - 1)
        pa = _point_at(a, t)
        pb = _point_at(b, t)
        d = haversine_m(pa[1], pa[0], pb[1], pb[0])
        total += d
        if d > max_d:
            max_d = d
    avg = total / samples
    # Distinct if they diverge ~350m on average, or peak split > 700m
    return avg < 350.0 and max_d < 700.0


def _point_at(coords: list, t: float) -> list[float]:
    if t <= 0:
        return coords[0]
    if t >= 1:
        return coords[-1]
    idx = t * (len(coords) - 1)
    i = int(idx)
    f = idx - i
    if i >= len(coords) - 1:
        return coords[-1]
    a, b = coords[i], coords[i + 1]
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]


def _with_safest_label(label: str) -> str:
    if label.lower().startswith("safest"):
        return label
    return label


def _http_get_json(url: str, timeout: int = 15):
    """
    GET JSON with SSL fallback.

    Some Windows Python installs fail OSRM/Nominatim TLS verification
    (expired/missing CA), which previously forced straight-line fallbacks.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    contexts = [None]
    try:
        contexts.append(ssl.create_default_context())
    except Exception:
        pass
    contexts.append(ssl._create_unverified_context())

    last_err = None
    for ctx in contexts:
        try:
            kwargs = {"timeout": timeout}
            if ctx is not None:
                kwargs["context"] = ctx
            with urllib.request.urlopen(req, **kwargs) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except ssl.SSLError as err:
            last_err = err
            continue
        except urllib.error.URLError as err:
            last_err = err
            # Retry only for SSL-related URLErrors
            reason = str(getattr(err, "reason", err))
            if "SSL" in reason or "certificate" in reason.lower():
                continue
            return None
        except (TimeoutError, json.JSONDecodeError, ValueError) as err:
            last_err = err
            return None
    return None
