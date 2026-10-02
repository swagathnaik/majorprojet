"""
Notification delivery tests (Meta WhatsApp Cloud API).
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
    # ==========================================
    # Meta WhatsApp Cloud API Gateway Tests
    # ==========================================
    wa_app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "DEMO_MODE": True,
            "WHATSAPP_CLOUD_API_TOKEN": "EAAX_test_meta_token_12345",
            "WHATSAPP_PHONE_NUMBER_ID": "105938472918274",
            "WHATSAPP_API_VERSION": "v21.0",
            "WHATSAPP_TEMPLATE_NAME": "hello_world",
            "WHATSAPP_TEMPLATE_LANG": "en_US",
            "SEND_WHATSAPP_ON_JOURNEY_START": False,
        }
    )

    with wa_app.app_context():
        # --- unit: phone normalization ---
        assert notify_mod._normalize_phone_e164_digits("9876543210") == "919876543210"
        assert notify_mod._normalize_phone_e164_digits("+91 9876543210") == "919876543210"
        assert notify_mod._normalize_phone_e164_digits("919901533228") == "919901533228"

        # --- unit: configuration check ---
        assert notify_mod._whatsapp_cloud_configured() is True
        assert (
            notify_mod._whatsapp_api_url()
            == "https://graph.facebook.com/v21.0/105938472918274/messages"
        )

        mock_resp_wa = MagicMock()
        mock_resp_wa.status = 200
        mock_resp_wa.read.return_value = json.dumps(
            {
                "messaging_product": "whatsapp",
                "contacts": [{"input": "919901533228", "wa_id": "919901533228"}],
                "messages": [{"id": "wamid.HBgMOTExOTkwMTUzMzIyOBUC..."}],
            }
        ).encode("utf-8")
        mock_resp_wa.__enter__ = lambda s: s
        mock_resp_wa.__exit__ = MagicMock(return_value=False)

        # --- unit: text message dispatch ---
        with patch("urllib.request.urlopen", return_value=mock_resp_wa) as mock_open:
            res = notify_mod._send_whatsapp_cloud_text("9901533228", "🚨 SOS Alert Text")
            assert mock_open.called
            req = mock_open.call_args_list[0][0][0]
            assert "105938472918274/messages" in req.full_url
            assert req.headers["Authorization"] == "Bearer EAAX_test_meta_token_12345"
            sent_data = json.loads(req.data.decode("utf-8"))
            assert sent_data["messaging_product"] == "whatsapp"
            assert sent_data["to"] == "919901533228"
            assert sent_data["type"] == "text"
            assert sent_data["text"]["body"] == "🚨 SOS Alert Text"

        # --- unit: location message dispatch ---
        with patch("urllib.request.urlopen", return_value=mock_resp_wa) as mock_open:
            notify_mod._send_whatsapp_cloud_location(
                "9901533228", 12.9716, 77.5946, "🚨 SOS Location", "Emergency Assistance"
            )
            req = mock_open.call_args_list[0][0][0]
            sent_data = json.loads(req.data.decode("utf-8"))
            assert sent_data["type"] == "location"
            assert sent_data["location"]["latitude"] == 12.9716
            assert sent_data["location"]["longitude"] == 77.5946

        # --- integration: user & contact setup ---
        client_wa = wa_app.test_client()
        r = client_wa.post(
            "/api/auth/register",
            json={"name": "WhatsApp User", "email": "wa@example.com", "password": "secret1"},
        )
        headers_wa = auth_header(r.get_json()["access_token"])
        c_res = client_wa.post(
            "/api/contacts",
            headers=headers_wa,
            json={"name": "Trusted Friend", "phone": "9901533228", "relationship": "Friend"},
        )
        wa_contact_id = c_res.get_json()["contact"]["id"]

        # --- test endpoint: POST /api/contacts/<id>/test-whatsapp ---
        with patch("urllib.request.urlopen", return_value=mock_resp_wa):
            r = client_wa.post(f"/api/contacts/{wa_contact_id}/test-whatsapp", headers=headers_wa)
        assert r.status_code == 200, r.data
        wa_test_deliv = r.get_json()["delivery"]
        assert wa_test_deliv["whatsapp_sent"] is True
        assert wa_test_deliv["whatsapp_provider"] == "meta_cloud_api"
        assert "whatsapp_cloud" in wa_test_deliv["channels"]

        # --- integration: manual SOS triggers WhatsApp Cloud API (Dual Mode) ---
        r = client_wa.post(
            "/api/journeys",
            headers=headers_wa,
            json={"dest_label": "Home", "start_lat": 12.97, "start_lng": 77.59},
        )
        jid_wa = r.get_json()["journey"]["id"]

        with patch("urllib.request.urlopen", return_value=mock_resp_wa) as mock_open:
            r = client_wa.post(
                f"/api/journeys/{jid_wa}/sos",
                headers=headers_wa,
                json={"reason": "Manual SOS", "lat": 12.9716, "lng": 77.5946},
            )
        assert r.status_code == 201, r.data
        sos_deliv = r.get_json()["notifications"][0]["delivery"]
        assert sos_deliv["whatsapp_sent"] is True
        assert sos_deliv["whatsapp_provider"] == "meta_cloud_api"
        assert "whatsapp_cloud" in sos_deliv["channels"]
        assert "whatsapp_cloud_location" in sos_deliv["channels"]
        assert mock_open.call_count >= 2

        # End active journey
        client_wa.post(f"/api/journeys/{jid_wa}/end", headers=headers_wa)

        # --- integration: automatic SOS triggers WhatsApp Cloud API ---
        r = client_wa.post(
            "/api/journeys",
            headers=headers_wa,
            json={"dest_label": "Office", "start_lat": 12.97, "start_lng": 77.59},
        )
        jid_wa2 = r.get_json()["journey"]["id"]
        r = client_wa.post(
            f"/api/journeys/{jid_wa2}/demo/simulate-anomaly",
            headers=headers_wa,
            json={"type": "prolonged_stop"},
        )
        chk_id = r.get_json()["active_safety_check"]["id"]

        with patch("urllib.request.urlopen", return_value=mock_resp_wa):
            r = client_wa.post(
                f"/api/safety-checks/{chk_id}/timeout",
                headers=headers_wa,
                json={"lat": 12.9716, "lng": 77.5946},
            )
        assert r.status_code == 200, r.data
        auto_wa_deliv = r.get_json()["notifications"][0]["delivery"]
        assert auto_wa_deliv["whatsapp_sent"] is True
        assert auto_wa_deliv["whatsapp_provider"] == "meta_cloud_api"
        assert "whatsapp_cloud" in auto_wa_deliv["channels"]
        assert "whatsapp_cloud_location" in auto_wa_deliv["channels"]

        print("All Meta WhatsApp Cloud API manual, automatic, and test notification tests passed.")


if __name__ == "__main__":
    run()
