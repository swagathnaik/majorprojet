"""
Unit and integration tests for Police Station API and data service.
Run: .venv\\Scripts\\python -m tests.test_police_stations
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services.police_data import get_all_police_stations, get_nearest_police_station


def run():
    app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
        }
    )

    with app.app_context():
        # 1. Service direct tests
        stations = get_all_police_stations()
        assert len(stations) >= 20, f"Expected >= 20 police stations, got {len(stations)}"
        
        # Verify Soladevanahalli PS is present (near Acharya Institute)
        sola = next((s for s in stations if "Soladevanahalli" in s["name"]), None)
        assert sola is not None, "Soladevanahalli Police Station should be present"
        assert sola["emergency_phone"] == "112"
        assert sola["verified"] is True

        # Test nearest to Acharya Institutes (13.0827, 77.4842)
        nearest = get_nearest_police_station(13.0827, 77.4842)
        assert nearest is not None
        assert "Soladevanahalli" in nearest["name"] or "Peenya" in nearest["name"]
        assert nearest["distance_km"] < 5.0
        assert "distance_str" in nearest

        # 2. API endpoints
        client = app.test_client()

        # GET /api/maps/police-stations
        res = client.get("/api/maps/police-stations")
        assert res.status_code == 200, res.data
        data = res.get_json()
        assert data["success"] is True
        assert len(data["police_stations"]) >= 20

        # GET /api/maps/nearest-police-station
        res = client.get("/api/maps/nearest-police-station?lat=13.0827&lng=77.4842")
        assert res.status_code == 200, res.data
        near_data = res.get_json()
        assert near_data["success"] is True
        assert near_data["nearest_station"]["id"] is not None

        # Nearest without coordinates should fail gracefully
        res = client.get("/api/maps/nearest-police-station")
        assert res.status_code == 400

        print("All Police Station service & API tests passed successfully.")


if __name__ == "__main__":
    run()
