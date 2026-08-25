"""
Notification delivery tests (including Vonage SMS).
Run: python -m tests.test_notify
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services import notify as notify_mod


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def run():
    app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "DEMO_MODE": True,
            "VONAGE_API_KEY": "719be850",
            "VONAGE_API_SECRET": "test_secret_123",
            "VONAGE_FROM_NUMBER": "Vonage APIs",
        }
    )

    with app.app_context():
        # --- unit: phone normalization for Vonage ---
        assert notify_mod._normalize_phone_e164_digits("9876543210") == "919876543210"
        assert notify_mod._normalize_phone_e164_digits("+91 9876543210") == "919876543210"

        # --- unit: Vonage SMS send (mocked HTTP) ---
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(
            {"messages": [{"status": "0", "message-id": "12345"}]}
        ).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            notify_mod._send_sms_vonage("9876543210", "SOS test message")
            assert mock_open.called
            req = mock_open.call_args[0][0]
            assert "rest.nexmo.com" in req.full_url
            sent_data = json.loads(req.data.decode("utf-8"))
            assert sent_data["api_key"] == "719be850"
            assert sent_data["to"] == "919876543210"

        # --- integration: automatic SOS triggers Vonage SMS ---
        client = app.test_client()
        r = client.post(
            "/api/auth/register",
            json={"name": "SMS User", "email": "sms@example.com", "password": "secret1"},
        )
        headers = auth_header(r.get_json()["access_token"])
        client.post(
            "/api/contacts",
            headers=headers,
            json={"name": "Emergency Contact", "phone": "9876543210", "relationship": "Mother"},
        )


        r = client.post(
            "/api/journeys",
            headers=headers,
            json={"dest_label": "Home", "start_lat": 12.97, "start_lng": 77.59},
        )
        j_res = r.get_json()
        jid = j_res["journey"]["id"]
        # Journey start should NOT send SMS via Vonage
        start_deliv = j_res["share"]["delivery"]
        assert start_deliv["sms_sent"] is False
        assert "sms_skipped_journey_started" in start_deliv["channels"]

        # --- integration 1: manual SOS triggers Vonage SMS ---
        with patch("urllib.request.urlopen", return_value=mock_resp):
            r = client.post(
                f"/api/journeys/{jid}/sos",
                headers=headers,
                json={"reason": "Manual emergency button pressed", "lat": 12.972, "lng": 77.592},
            )
        assert r.status_code == 201, r.data
        manual_body = r.get_json()
        assert manual_body["sos"]["type"] == "manual"
        assert len(manual_body["notifications"]) == 1
        manual_delivery = manual_body["notifications"][0]["delivery"]
        assert manual_delivery["sms_sent"] is True
        assert manual_delivery["sms_provider"] == "vonage"
        assert "sms" in manual_delivery["channels"]

        # End active journey jid so a new one can be started
        client.post(f"/api/journeys/{jid}/end", headers=headers)

        # --- integration 2: automatic SOS triggers Vonage SMS ---
        r = client.post(
            "/api/journeys",
            headers=headers,
            json={"dest_label": "Work", "start_lat": 12.97, "start_lng": 77.59},
        )
        jid2 = r.get_json()["journey"]["id"]

        r = client.post(
            f"/api/journeys/{jid2}/demo/simulate-anomaly",
            headers=headers,
            json={"type": "prolonged_stop"},
        )

        check_id = r.get_json()["active_safety_check"]["id"]

        with patch("urllib.request.urlopen", return_value=mock_resp):
            r = client.post(
                f"/api/safety-checks/{check_id}/timeout",
                headers=headers,
                json={"lat": 12.971, "lng": 77.591},
            )
        assert r.status_code == 200, r.data
        body = r.get_json()
        assert body["sos"]["type"] == "automatic"
        assert len(body["notifications"]) == 1
        delivery = body["notifications"][0]["delivery"]
        assert delivery["sms_sent"] is True
        assert delivery["sms_provider"] == "vonage"
        assert "sms" in delivery["channels"]


        print("All Vonage manual and automatic notification tests passed.")


if __name__ == "__main__":
    run()

