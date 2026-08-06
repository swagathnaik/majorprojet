"""
Phase 4 – GPS / journey location tests.
Run: python -m tests.test_locations
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def run():
    app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
        }
    )

    with app.app_context():
        client = app.test_client()

        r = client.post(
            "/api/auth/register",
            json={"name": "Geo", "email": "geo@example.com", "password": "secret1"},
        )
        assert r.status_code == 201, r.data
        token = r.get_json()["access_token"]
        headers = auth_header(token)

        r = client.post(
            "/api/contacts",
            headers=headers,
            json={"name": "Mom", "phone": "9876543210", "relationship": "Mother"},
        )
        assert r.status_code == 201

        # No active journey
        r = client.get("/api/journeys/active", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["journey"] is None

        # Start journey with start coords
        r = client.post(
            "/api/journeys",
            headers=headers,
            json={"start_lat": 12.9716, "start_lng": 77.5946, "dest_label": "Campus"},
        )
        assert r.status_code == 201, r.data
        journey = r.get_json()["journey"]
        assert journey["status"] == "active"
        jid = journey["id"]

        # Cannot start second active journey
        r = client.post("/api/journeys", headers=headers, json={})
        assert r.status_code == 409

        # Post location
        r = client.post(
            f"/api/journeys/{jid}/locations",
            headers=headers,
            json={
                "lat": 12.9720,
                "lng": 77.5950,
                "accuracy": 12.5,
                "speed": 1.2,
                "heading": 90,
                "recorded_at": "2026-08-04T12:00:00Z",
            },
        )
        assert r.status_code == 201, r.data
        loc = r.get_json()["location"]
        assert loc["lat"] == 12.9720
        assert loc["speed"] == 1.2

        # Invalid coords
        r = client.post(
            f"/api/journeys/{jid}/locations",
            headers=headers,
            json={"lat": 200, "lng": 10},
        )
        assert r.status_code == 400

        # List locations
        r = client.get(f"/api/journeys/{jid}/locations", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["count"] == 1

        # End journey
        r = client.post(f"/api/journeys/{jid}/end", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["journey"]["status"] == "ended"

        # Cannot post after end
        r = client.post(
            f"/api/journeys/{jid}/locations",
            headers=headers,
            json={"lat": 12.97, "lng": 77.59},
        )
        assert r.status_code == 400

        print("All Phase 4 location tests passed.")


if __name__ == "__main__":
    run()
