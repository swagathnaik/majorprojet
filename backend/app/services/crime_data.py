"""
Crime hotspot loading + route safety scoring.

Primary source: Kaggle ``sudhanvahg/indian-crimes-dataset`` (via kagglehub).
The CSV is city-level (no lat/lng), so we map cities to coordinates and expand
Bangalore records across known neighbourhoods for a usable journey heatmap.

IMPORTANT: Historical crime ≠ current danger. Absence of points ≠ safe.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.utils.geo import haversine_m

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE_PATH = DATA_DIR / "crime_hotspots_kaggle.json"
FALLBACK_PATH = DATA_DIR / "crime_hotspots.json"
INFLUENCE_RADIUS_M = 400.0

KAGGLE_DATASET = "sudhanvahg/indian-crimes-dataset"
KAGGLE_FILE = "crime_dataset_india.csv"

# Approximate city centres for heatmap placement
CITY_COORDS: dict[str, tuple[float, float]] = {
    "delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
    "kolkata": (22.5726, 88.3639),
    "chennai": (13.0827, 80.2707),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "lucknow": (26.8467, 80.9462),
    "kanpur": (26.4499, 80.3319),
    "surat": (21.1702, 72.8311),
    "nagpur": (21.1458, 79.0882),
    "agra": (27.1767, 78.0081),
    "ludhiana": (30.9010, 75.8573),
    "patna": (25.5941, 85.1376),
    "indore": (22.7196, 75.8577),
    "bhopal": (23.2599, 77.4126),
    "vadodara": (22.3072, 73.1812),
    "coimbatore": (11.0168, 76.9558),
    "kochi": (9.9312, 76.2673),
    "visakhapatnam": (17.6868, 83.2185),
    "varanasi": (25.3176, 82.9739),
    "ghaziabad": (28.6692, 77.4538),
    "faridabad": (28.4089, 77.3178),
    "meerut": (28.9845, 77.7064),
    "rajkot": (22.3039, 70.8022),
    "srinagar": (34.0837, 74.7973),
    "amritsar": (31.6340, 74.8723),
    "chandigarh": (30.7333, 76.7794),
    "guwahati": (26.1445, 91.7362),
    "thiruvananthapuram": (8.5241, 76.9366),
    "mysore": (12.2958, 76.6394),
    "mysuru": (12.2958, 76.6394),
}

# Neighbourhoods used to spread Bangalore crime rows onto the map
BANGALORE_NEIGHBOURHOODS: list[tuple[str, float, float]] = [
    ("MG Road", 12.9750, 77.6060),
    ("Indiranagar", 12.9784, 77.6408),
    ("Koramangala", 12.9352, 77.6245),
    ("HSR Layout", 12.9141, 77.6387),
    ("Whitefield", 12.9698, 77.7500),
    ("Electronic City", 12.8450, 77.6600),
    ("Jayanagar", 12.9300, 77.5800),
    ("Malleshwaram", 13.0020, 77.5700),
    ("Rajajinagar", 12.9850, 77.5500),
    ("Hebbal", 13.0358, 77.5970),
    ("BTM Layout", 12.9166, 77.6101),
    ("Marathahalli", 12.9592, 77.6974),
    ("Majestic", 12.9780, 77.5720),
    ("Banashankari", 12.9250, 77.5500),
    ("Yelahanka", 13.1005, 77.5963),
    ("RT Nagar", 13.0200, 77.5950),
    ("Frazer Town", 12.9980, 77.6150),
    ("Ulsoor", 12.9780, 77.6200),
    ("Domlur", 12.9600, 77.6400),
    ("Kalyan Nagar", 13.0220, 77.6400),
    ("CV Raman Nagar", 12.9850, 77.6600),
    ("Vijayanagar", 12.9630, 77.5370),
    ("Yeswanthpur", 13.0280, 77.5400),
    ("Basavanagudi", 12.9420, 77.5700),
    ("Sarjapur", 12.9100, 77.6800),
    ("Bellandur", 12.9300, 77.6700),
    ("JP Nagar", 12.9080, 77.5850),
    ("Peenya", 13.0300, 77.5200),
    ("Kengeri", 12.9100, 77.4800),
    ("Chikkabanavara", 13.0800, 77.5000),
]

SEVERITY = {
    "homicide": 1.0,
    "sexual assault": 0.98,
    "kidnapping": 0.95,
    "assault": 0.9,
    "domestic violence": 0.88,
    "firearm offense": 0.92,
    "robbery": 0.85,
    "extortion": 0.82,
    "burglary": 0.78,
    "illegal possession": 0.72,
    "vandalism": 0.55,
    "fraud": 0.5,
    "identity theft": 0.48,
    "counterfeiting": 0.45,
    "public intoxication": 0.4,
    "traffic violation": 0.35,
    "fire accident": 0.6,
}


@lru_cache(maxsize=1)
def load_crime_dataset() -> dict:
    """Load hotspots: cache → Kaggle build → synthetic fallback."""
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("hotspots"):
                return data
        except (OSError, json.JSONDecodeError):
            pass

    built = _build_from_kaggle()
    if built and built.get("hotspots"):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(built, f)
        except OSError:
            pass
        return built

    with open(FALLBACK_PATH, encoding="utf-8") as f:
        return json.load(f)


def reload_crime_dataset() -> dict:
    """Force rebuild from Kaggle (clears cache)."""
    load_crime_dataset.cache_clear()
    if CACHE_PATH.exists():
        try:
            CACHE_PATH.unlink()
        except OSError:
            pass
    return load_crime_dataset()


def get_hotspots() -> list[dict]:
    return load_crime_dataset().get("hotspots", [])


def get_crime_meta() -> dict:
    return load_crime_dataset().get("meta", {})


def score_route_lnglat(coords_lnglat: list[list[float]]) -> dict:
    """
    Score a route given GeoJSON-order coordinates: [[lng, lat], ...].
    Returns safety_score 0–100 (higher = lower historical risk indicator).
    """
    if not coords_lnglat or len(coords_lnglat) < 2:
        return {
            "safety_score": 50,
            "risk_indicator": "unknown",
            "crime_exposure": 0,
            "sampled_points": 0,
            "distance_m": 0,
            "note": "Not enough geometry to score.",
        }

    points = [(float(c[1]), float(c[0])) for c in coords_lnglat]
    distance_m = 0.0
    for i in range(1, len(points)):
        distance_m += haversine_m(
            points[i - 1][0], points[i - 1][1], points[i][0], points[i][1]
        )

    samples = _sample_points(points, step_m=80.0, max_samples=100)
    hotspots = get_hotspots()
    exposure = 0.0
    for slat, slng in samples:
        for h in hotspots:
            d = haversine_m(slat, slng, h["lat"], h["lng"])
            if d <= INFLUENCE_RADIUS_M:
                w = 1.0 - (d / INFLUENCE_RADIUS_M)
                exposure += float(h.get("intensity", 0.5)) * w

    norm = exposure / max(1, len(samples))
    risk = min(100.0, norm * 48.0)
    safety_score = round(max(0.0, 100.0 - risk), 1)

    if safety_score >= 75:
        indicator = "lower_historical_risk"
    elif safety_score >= 50:
        indicator = "moderate_historical_risk"
    else:
        indicator = "higher_historical_risk"

    return {
        "safety_score": safety_score,
        "risk_indicator": indicator,
        "crime_exposure": round(exposure, 3),
        "sampled_points": len(samples),
        "distance_m": round(distance_m, 1),
        "note": (
            "Safety Score uses Kaggle Indian Crimes Dataset mapped to map points "
            "— historical risk indicator only, not a guarantee of safety."
        ),
    }


def _build_from_kaggle() -> dict | None:
    try:
        import kagglehub
        from kagglehub import KaggleDatasetAdapter
    except ImportError:
        return None

    try:
        # Prefer new API name; fall back for older kagglehub
        if hasattr(kagglehub, "dataset_load"):
            df = kagglehub.dataset_load(
                KaggleDatasetAdapter.PANDAS, KAGGLE_DATASET, KAGGLE_FILE
            )
        else:
            df = kagglehub.load_dataset(
                KaggleDatasetAdapter.PANDAS, KAGGLE_DATASET, KAGGLE_FILE
            )
    except Exception:
        return None

    if df is None or getattr(df, "empty", True):
        return None

    hotspots: list[dict] = []
    city_col = _find_col(df, ["City", "city"])
    desc_col = _find_col(df, ["Crime Description", "CrimeDescription", "crime_description"])
    domain_col = _find_col(df, ["Crime Domain", "CrimeDomain", "crime_domain"])
    report_col = _find_col(df, ["Report Number", "ReportNumber", "report_number"])

    if not city_col:
        return None

    # 1) Aggregate other cities → one weighted centroid point each
    city_stats: dict[str, dict] = {}
    bangalore_rows = []

    for _, row in df.iterrows():
        city_raw = str(row.get(city_col, "")).strip()
        city_key = city_raw.lower()
        desc = str(row.get(desc_col, "") if desc_col else "").strip()
        domain = str(row.get(domain_col, "") if domain_col else "").strip()
        intensity = _severity(desc, domain)
        report_id = row.get(report_col, 0) if report_col else 0

        if city_key in ("bangalore", "bengaluru"):
            bangalore_rows.append((report_id, desc, domain, intensity))
            continue

        coords = CITY_COORDS.get(city_key)
        if not coords:
            continue
        st = city_stats.setdefault(
            city_key, {"lat": coords[0], "lng": coords[1], "count": 0, "intensity_sum": 0.0, "label": city_raw}
        )
        st["count"] += 1
        st["intensity_sum"] += intensity

    max_city = max((s["count"] for s in city_stats.values()), default=1)
    for st in city_stats.values():
        avg_i = st["intensity_sum"] / max(1, st["count"])
        vol = min(1.0, st["count"] / max_city)
        hotspots.append(
            {
                "lat": round(st["lat"], 6),
                "lng": round(st["lng"], 6),
                "intensity": round(0.35 + 0.65 * avg_i * (0.4 + 0.6 * vol), 3),
                "type": "city_aggregate",
                "label": f"{st['label']} ({st['count']} reports)",
                "count": st["count"],
            }
        )

    # 2) Expand Bangalore crimes across neighbourhoods (dense local heatmap)
    if bangalore_rows:
        # Cap points for map performance while keeping coverage
        step = max(1, len(bangalore_rows) // 900)
        for idx, (report_id, desc, domain, intensity) in enumerate(bangalore_rows):
            if idx % step != 0:
                continue
            seed = f"{report_id}-{desc}-{idx}"
            n_idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(
                BANGALORE_NEIGHBOURHOODS
            )
            name, blat, blng = BANGALORE_NEIGHBOURHOODS[n_idx]
            # Small deterministic jitter so points aren't stacked
            j1 = (int(hashlib.md5((seed + "a").encode()).hexdigest(), 16) % 1000) / 1000.0
            j2 = (int(hashlib.md5((seed + "b").encode()).hexdigest(), 16) % 1000) / 1000.0
            lat = blat + (j1 - 0.5) * 0.012
            lng = blng + (j2 - 0.5) * 0.012
            hotspots.append(
                {
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                    "intensity": round(float(intensity), 3),
                    "type": (desc or domain or "crime").lower()[:48],
                    "label": f"Bangalore · {name} · {desc or domain or 'crime'}",
                }
            )

    return {
        "meta": {
            "title": "Indian Crimes Dataset (Kaggle)",
            "source": KAGGLE_DATASET,
            "file": KAGGLE_FILE,
            "city": "India (Bangalore neighbourhood expansion for journey map)",
            "records_used": int(len(df)),
            "hotspot_count": len(hotspots),
            "bangalore_reports": len(bangalore_rows),
            "disclaimer": (
                "Crime points derived from Kaggle sudhanvahg/indian-crimes-dataset. "
                "City-level records are mapped to approximate coordinates; Bangalore "
                "rows are distributed across neighbourhoods for heatmap visualization. "
                "Historical crime does not guarantee current danger."
            ),
        },
        "hotspots": hotspots,
    }


def _find_col(df, names: list[str]):
    cols = {str(c).strip().lower(): c for c in df.columns}
    for n in names:
        if n.lower() in cols:
            return cols[n.lower()]
    return None


def _severity(desc: str, domain: str) -> float:
    key = (desc or "").strip().lower()
    if key in SEVERITY:
        return SEVERITY[key]
    d = (domain or "").strip().lower()
    if "violent" in d:
        return 0.9
    if "traffic" in d:
        return 0.4
    if "fire" in d:
        return 0.6
    return 0.55


def _sample_points(points: list[tuple[float, float]], step_m: float, max_samples: int):
    if not points:
        return []
    samples = [points[0]]
    acc = 0.0
    for i in range(1, len(points)):
        seg = haversine_m(
            points[i - 1][0], points[i - 1][1], points[i][0], points[i][1]
        )
        acc += seg
        if acc >= step_m:
            samples.append(points[i])
            acc = 0.0
            if len(samples) >= max_samples:
                break
    if samples[-1] != points[-1]:
        samples.append(points[-1])
    return samples
