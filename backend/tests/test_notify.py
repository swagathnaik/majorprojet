"""
Notification / Fast2SMS tests.
Run: python -m tests.test_notify
"""
import io
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
            "FAST2SMS_API_KEY": "test-fast2sms-key",
        }
    )

    with app.app_context():
        # --- unit: phone normalization ---
        assert notify_mod._normalize_phone_india_10("9901533228") == "9901533228"
        assert notify_mod._normalize_phone_india_10("+91 9901533228") == "9901533228"
        assert notify_mod._normalize_phone_india_10("919901533228") == "9901533228"

        # --- unit: Fast2SMS send (mocked HTTP) ---
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"return": True, "request_id": "abc", "message": ["Message sent successfully"]}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            notify_mod._send_sms_fast2sms("9901533228", "SOS test message")
            assert mock_open.called
            req = mock_open.call_args[0][0]
            assert req.get_header("Authorization") == "test-fast2sms-key"

        # --- integration: automatic SOS uses Fast2SMS ---
        client = app.test_client()
        r = client.post(
            "/api/auth/register",
            json={"name": "SMS User", "email": "sms@example.com", "password": "secret1"},
        )
        headers = auth_header(r.get_json()["access_token"])
        client.post(
            "/api/contacts",
            headers=headers,
            json={"name": "Mom", "phone": "9901533228", "relationship": "Mother"},
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
        assert delivery["sms_provider"] == "fast2sms"
        assert "sms" in delivery["channels"]

        print("All notification / Fast2SMS tests passed.")


if __name__ == "__main__":
    run()
