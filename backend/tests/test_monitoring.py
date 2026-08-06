"""
Phase 7 – journey monitoring tests.
Run: python -m tests.test_monitoring
"""
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models.location import LocationLog


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def run():
    app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "STOP_THRESHOLD_SEC": 60,
            "DEVIATION_THRESHOLD_M": 50,
            "LOST_SIGNAL_SEC": 75,
        }
    )

    with app.app_context():
        client = app.test_client()

        r = client.post(
            "/api/auth/register",
            json={"name": "Mon", "email": "mon@example.com", "password": "secret1"},
        )
        token = r.get_json()["access_token"]
        headers = auth_header(token)

        client.post(
            "/api/contacts",
            headers=headers,
            json={"name": "Mom", "phone": "9876543210", "relationship": "Mother"},
        )

        r = client.post(
            "/api/journeys",
            headers=headers,
            json={
                "dest_label": "Park",
                "start_lat": 12.9700,
                "start_lng": 77.5900,
                "dest_lat": 12.9800,
                "dest_lng": 77.6000,
            },
        )
        assert r.status_code == 201, r.data
        jid = r.get_json()["journey"]["id"]

        # Empty monitoring
        r = client.get(f"/api/journeys/{jid}/monitoring", headers=headers)
        assert r.status_code == 200
        mon = r.get_json()["monitoring"]
        assert mon["movement_status"] == "waiting_for_gps"
        assert mon["point_count"] == 0

        # Moving points
        base = datetime.now(timezone.utc) - timedelta(seconds=30)
        for i, (lat, lng, spd) in enumerate(
            [
                (12.9700, 77.5900, 1.2),
                (12.9705, 77.5905, 1.3),
                (12.9710, 77.5910, 1.4),
            ]
        ):
            r = client.post(
                f"/api/journeys/{jid}/locations",
                headers=headers,
                json={
                    "lat": lat,
                    "lng": lng,
                    "speed": spd,
                    "heading": 45,
                    "recorded_at": (base + timedelta(seconds=i * 5)).isoformat(),
                },
            )
            assert r.status_code == 201, r.data
            assert "monitoring" in r.get_json()

        r = client.get(f"/api/journeys/{jid}/monitoring", headers=headers)
        mon = r.get_json()["monitoring"]
        assert mon["point_count"] == 3
        assert mon["movement_status"] == "moving"
        assert mon["speed_mps"] is not None
        assert mon["distance_traveled_m"] > 0
        assert mon["distance_to_dest_m"] is not None
        assert mon["heading_label"] is not None
        assert mon["eta_sec"] is not None

        # Simulate stopped streak by inserting slow recent points
        stop_base = datetime.now(timezone.utc) - timedelta(seconds=40)
        journey_locs = LocationLog.query.filter_by(journey_id=jid).all()
        # Add stationary points at last location
        last = journey_locs[-1]
        for i in range(4):
            db.session.add(
                LocationLog(
                    journey_id=jid,
                    lat=last.lat,
                    lng=last.lng,
                    speed=0.0,
                    heading=45,
                    recorded_at=stop_base + timedelta(seconds=i * 10),
                )
            )
        db.session.commit()

        r = client.get(f"/api/journeys/{jid}/monitoring", headers=headers)
        mon = r.get_json()["monitoring"]
        assert mon["movement_status"] in ("stopped", "slow_or_uncertain")
        assert mon["stop_duration_sec"] >= 0

        print("All Phase 7 monitoring tests passed.")


if __name__ == "__main__":
    run()
