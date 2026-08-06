"""
Phase 9 – safety verification tests.
Run: python -m tests.test_safety
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _start_with_anomaly(client, headers):
    client.post(
        "/api/contacts",
        headers=headers,
        json={"name": "Mom", "phone": "9876543210", "relationship": "Mother"},
    )
    r = client.post(
        "/api/journeys",
        headers=headers,
        json={"dest_label": "Home", "start_lat": 12.97, "start_lng": 77.59},
    )
    jid = r.get_json()["journey"]["id"]
    r = client.post(
        f"/api/journeys/{jid}/demo/simulate-anomaly",
        headers=headers,
        json={"type": "prolonged_stop"},
    )
    assert r.status_code == 201, r.data
    check_id = r.get_json()["active_safety_check"]["id"]
    return jid, check_id


def run():
    app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "DEMO_MODE": True,
            "SAFETY_RESPONSE_SEC": 15,
            "SOS_COUNTDOWN_SEC": 10,
        }
    )

    with app.app_context():
        client = app.test_client()

        # --- Safe response ---
        r = client.post(
            "/api/auth/register",
            json={"name": "Safe", "email": "safe@example.com", "password": "secret1"},
        )
        headers = auth_header(r.get_json()["access_token"])
        jid, check_id = _start_with_anomaly(client, headers)

        r = client.post(
            f"/api/safety-checks/{check_id}/respond",
            headers=headers,
            json={"response": "safe"},
        )
        assert r.status_code == 200, r.data
        body = r.get_json()
        assert body["safety_check"]["status"] == "safe"
        assert body["sos"] is None
        assert body["journey"]["status"] == "active"

        mon = client.get(f"/api/journeys/{jid}/monitoring", headers=headers).get_json()
        assert mon["active_safety_check"] is None
        assert mon["open_anomalies"] == []

        # --- Need help ---
        client.post(f"/api/journeys/{jid}/end", headers=headers)
        r = client.post(
            "/api/auth/register",
            json={"name": "Help", "email": "help@example.com", "password": "secret1"},
        )
        headers2 = auth_header(r.get_json()["access_token"])
        jid2, check2 = _start_with_anomaly(client, headers2)

        r = client.post(
            f"/api/safety-checks/{check2}/respond",
            headers=headers2,
            json={"response": "need_help", "lat": 12.97, "lng": 77.59},
        )
        assert r.status_code == 200, r.data
        body = r.get_json()
        assert body["safety_check"]["status"] == "need_help"
        assert body["sos"]["type"] == "manual"
        assert body["journey"]["status"] == "sos"

        # --- Timeout → automatic SOS ---
        r = client.post(
            "/api/auth/register",
            json={"name": "Time", "email": "time@example.com", "password": "secret1"},
        )
        headers3 = auth_header(r.get_json()["access_token"])
        jid3, check3 = _start_with_anomaly(client, headers3)

        r = client.post(
            f"/api/safety-checks/{check3}/timeout",
            headers=headers3,
            json={"lat": 12.971, "lng": 77.591},
        )
        assert r.status_code == 200, r.data
        body = r.get_json()
        assert body["safety_check"]["status"] == "timeout"
        assert body["sos"]["type"] == "automatic"
        assert body["journey"]["status"] == "sos"
        assert len(body.get("notifications") or []) == 1
        assert body["notifications"][0]["contact_name"] == "Mom"

        # --- Automatic SOS notifies all contacts ---
        r = client.post(
            "/api/auth/register",
            json={"name": "Multi", "email": "multi@example.com", "password": "secret1"},
        )
        headers5 = auth_header(r.get_json()["access_token"])
        client.post(
            "/api/contacts",
            headers=headers5,
            json={"name": "Mom", "phone": "9876543210", "relationship": "Mother"},
        )
        client.post(
            "/api/contacts",
            headers=headers5,
            json={"name": "Dad", "phone": "9876543211", "relationship": "Father"},
        )
        r = client.post(
            "/api/journeys",
            headers=headers5,
            json={"dest_label": "Home", "start_lat": 12.97, "start_lng": 77.59},
        )
        jid5 = r.get_json()["journey"]["id"]
        r = client.post(
            f"/api/journeys/{jid5}/demo/simulate-anomaly",
            headers=headers5,
            json={"type": "prolonged_stop"},
        )
        check5 = r.get_json()["active_safety_check"]["id"]
        r = client.post(
            f"/api/safety-checks/{check5}/timeout",
            headers=headers5,
            json={"lat": 12.971, "lng": 77.591},
        )
        assert r.status_code == 200, r.data
        body5 = r.get_json()
        assert len(body5["notifications"]) == 2
        notified = {n["contact_name"] for n in body5["notifications"]}
        assert notified == {"Mom", "Dad"}

        # --- Cancel countdown ---
        r = client.post(
            "/api/auth/register",
            json={"name": "Cancel", "email": "cancel@example.com", "password": "secret1"},
        )
        headers4 = auth_header(r.get_json()["access_token"])
        _, check4 = _start_with_anomaly(client, headers4)
        r = client.post(
            f"/api/safety-checks/{check4}/cancel-countdown",
            headers=headers4,
        )
        assert r.status_code == 200, r.data
        assert r.get_json()["safety_check"]["status"] == "cancelled"
        assert r.get_json()["sos"] is None

        print("All Phase 9 safety verification tests passed.")


if __name__ == "__main__":
    run()
