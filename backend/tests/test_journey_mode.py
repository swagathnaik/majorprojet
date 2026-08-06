"""
Phase 5 – Safe Journey Mode lifecycle tests.
Run: python -m tests.test_journey_mode
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
            json={"name": "Jaya", "email": "jaya@example.com", "password": "secret1"},
        )
        assert r.status_code == 201, r.data
        token = r.get_json()["access_token"]
        headers = auth_header(token)

        # Cannot start without contacts
        r = client.post(
            "/api/journeys",
            headers=headers,
            json={"dest_label": "Library", "start_lat": 12.97, "start_lng": 77.59},
        )
        assert r.status_code == 400

        r = client.post(
            "/api/contacts",
            headers=headers,
            json={"name": "Mom", "phone": "9876543210", "relationship": "Mother"},
        )
        assert r.status_code == 201
        contact_id = r.get_json()["contact"]["id"]

        # Destination required
        r = client.post(
            "/api/journeys",
            headers=headers,
            json={"start_lat": 12.97, "start_lng": 77.59},
        )
        assert r.status_code == 400

        # Start Safe Journey
        r = client.post(
            "/api/journeys",
            headers=headers,
            json={
                "dest_label": "College library",
                "dest_lat": 12.98,
                "dest_lng": 77.60,
                "start_lat": 12.97,
                "start_lng": 77.59,
                "active_contact_id": contact_id,
            },
        )
        assert r.status_code == 201, r.data
        journey = r.get_json()["journey"]
        assert journey["status"] == "active"
        assert journey["contact"]["name"] == "Mom"
        jid = journey["id"]

        # Pause
        r = client.post(f"/api/journeys/{jid}/pause", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["journey"]["status"] == "paused"

        # Cannot post location while paused
        r = client.post(
            f"/api/journeys/{jid}/locations",
            headers=headers,
            json={"lat": 12.971, "lng": 77.591},
        )
        assert r.status_code == 400

        # Resume
        r = client.post(f"/api/journeys/{jid}/resume", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["journey"]["status"] == "active"

        r = client.post(
            f"/api/journeys/{jid}/locations",
            headers=headers,
            json={"lat": 12.971, "lng": 77.591},
        )
        assert r.status_code == 201

        # Manual SOS shell
        r = client.post(
            f"/api/journeys/{jid}/sos",
            headers=headers,
            json={"lat": 12.971, "lng": 77.591},
        )
        assert r.status_code == 201, r.data
        body = r.get_json()
        assert body["sos"]["type"] == "manual"
        assert body["journey"]["status"] == "sos"

        # End after SOS
        r = client.post(f"/api/journeys/{jid}/end", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["journey"]["status"] == "ended"

        # New journey then cancel
        r = client.post(
            "/api/journeys",
            headers=headers,
            json={
                "dest_label": "Bus stop",
                "start_lat": 12.97,
                "start_lng": 77.59,
                "active_contact_id": contact_id,
            },
        )
        jid2 = r.get_json()["journey"]["id"]
        r = client.post(f"/api/journeys/{jid2}/cancel", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["journey"]["status"] == "cancelled"

        print("All Phase 5 Safe Journey tests passed.")


if __name__ == "__main__":
    run()
