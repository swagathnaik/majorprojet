"""
Phase 8 – anomaly detection tests.
Run: python -m tests.test_anomalies
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
            "DEMO_MODE": True,
            "STOP_THRESHOLD_SEC": 30,
            "DEVIATION_THRESHOLD_M": 40,
            "LOST_SIGNAL_SEC": 20,
            "ANOMALY_COOLDOWN_SEC": 60,
        }
    )

    with app.app_context():
        client = app.test_client()

        r = client.post(
            "/api/auth/register",
            json={"name": "Ano", "email": "ano@example.com", "password": "secret1"},
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
                "dest_label": "Gate",
                "start_lat": 12.9700,
                "start_lng": 77.5900,
                "dest_lat": 12.9800,
                "dest_lng": 77.6000,
            },
        )
        jid = r.get_json()["journey"]["id"]

        # Moving history (recent timestamps so lost_signal does not fire)
        base = datetime.now(timezone.utc) - timedelta(seconds=50)
        for i in range(3):
            client.post(
                f"/api/journeys/{jid}/locations",
                headers=headers,
                json={
                    "lat": 12.9700 + i * 0.0004,
                    "lng": 77.5900 + i * 0.0004,
                    "speed": 1.2,
                    "recorded_at": (base + timedelta(seconds=i * 5)).isoformat(),
                },
            )

        # Prolonged stop points ending "now"
        stop_base = datetime.now(timezone.utc) - timedelta(seconds=40)
        last_lat, last_lng = 12.9708, 77.5908
        for i in range(5):
            db.session.add(
                LocationLog(
                    journey_id=jid,
                    lat=last_lat,
                    lng=last_lng,
                    speed=0.0,
                    recorded_at=stop_base + timedelta(seconds=i * 10),
                )
            )
        db.session.commit()

        # Clear any anomaly created during seeding so prolonged_stop can fire cleanly
        from app.models.anomaly import Anomaly
        from app.models.safety_check import SafetyCheck

        SafetyCheck.query.filter_by(journey_id=jid).delete()
        Anomaly.query.filter_by(journey_id=jid).delete()
        db.session.commit()

        r = client.get(f"/api/journeys/{jid}/monitoring", headers=headers)
        assert r.status_code == 200, r.data
        body = r.get_json()
        assert body["monitoring"]["movement_status"] == "stopped"
        assert any(a["type"] == "prolonged_stop" for a in body["open_anomalies"]), body
        assert body["active_safety_check"] is not None
        assert body["active_safety_check"]["status"] == "pending"

        # Demo simulate another type after we can't pile on while pending –
        # first check list
        r = client.get(f"/api/journeys/{jid}/anomalies", headers=headers)
        assert r.status_code == 200
        assert len(r.get_json()["anomalies"]) >= 1

        # New journey for demo simulate
        client.post(f"/api/journeys/{jid}/end", headers=headers)
        r = client.post(
            "/api/journeys",
            headers=headers,
            json={"dest_label": "Demo", "start_lat": 12.97, "start_lng": 77.59},
        )
        jid2 = r.get_json()["journey"]["id"]
        r = client.post(
            f"/api/journeys/{jid2}/demo/simulate-anomaly",
            headers=headers,
            json={"type": "route_deviation"},
        )
        assert r.status_code == 201, r.data
        assert r.get_json()["anomaly"]["type"] == "route_deviation"

        print("All Phase 8 anomaly tests passed.")


if __name__ == "__main__":
    run()
