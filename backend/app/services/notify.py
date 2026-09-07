"""
Trusted-contact notifications (Phase 10–12).

Vonage SMS gateway for SOS alerts.
Direct WhatsApp and SMS 1-click fallback links.
In-app notification logging.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, request

from app.models.contact import EmergencyContact
from app.models.journey import Journey
from app.models.sos import SosAlert
from app.models.user import User

LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "notification_log.jsonl"


def frontend_base_url() -> str:
    """Prefer browser Origin, then FRONTEND_URL / CORS for share links."""
    origin = (request.headers.get("Origin") or "").rstrip("/")
    if origin:
        return origin
    configured = (current_app.config.get("FRONTEND_URL") or "").rstrip("/")
    if configured:
        return configured
    origins = current_app.config.get("CORS_ORIGINS") or []
    if origins:
        return str(origins[0]).rstrip("/")
    return "http://127.0.0.1:5173"


def journey_share_url(journey: Journey) -> str:
    return f"{frontend_base_url()}/s/{journey.share_token}"


def notify_journey_started(journey: Journey, contact: EmergencyContact | None) -> dict:
    """Auto-share secure tracking link with trusted contact when journey starts."""
    user = User.query.get(journey.user_id)
    share_url = journey_share_url(journey)
    payload = {
        "event": "journey_started",
        "channel": "share_link",
        "at": datetime.now(timezone.utc).isoformat(),
        "journey_id": journey.id,
        "traveler": user.name if user else "Traveler",
        "destination": journey.dest_label,
        "contact_id": contact.id if contact else None,
        "contact_name": contact.name if contact else None,
        "contact_phone": contact.phone if contact else None,
        "share_url": share_url,
        "message": (
            f"{user.name if user else 'A SafeRoute user'} started a Safe Journey "
            f"to {journey.dest_label}. Live tracking: {share_url}"
        ),
    }
    delivery = _deliver(payload, contact)
    payload["delivery"] = delivery
    _append_log(payload)
    return payload


def notify_sos(
    journey: Journey,
    alert: SosAlert,
    contact: EmergencyContact | None,
) -> dict:
    """Notify one trusted contact when SOS is created."""
    user = User.query.get(journey.user_id)
    share_url = journey_share_url(journey)
    loc = ""
    if alert.lat is not None and alert.lng is not None:
        loc = f" Location: {alert.lat:.5f}, {alert.lng:.5f}."
    payload = {
        "event": "sos_alert",
        "channel": "emergency",
        "at": datetime.now(timezone.utc).isoformat(),
        "journey_id": journey.id,
        "sos_id": alert.id,
        "sos_type": alert.type,
        "reason": alert.trigger_reason,
        "lat": alert.lat,
        "lng": alert.lng,
        "traveler": user.name if user else "Traveler",
        "contact_id": contact.id if contact else None,
        "contact_name": contact.name if contact else None,
        "contact_phone": contact.phone if contact else None,
        "share_url": share_url,
        "call_112_hint": "Optional: dial 112 (India emergency) if life is at risk.",
        "message": (
            f"SOS for {user.name if user else 'traveler'} "
            f"({alert.type}): {alert.trigger_reason or 'emergency'}."
            f"{loc} Track: {share_url}"
        ),
    }
    delivery = _deliver(payload, contact)
    if delivery.get("network") == "degraded":
        delivery["fallback"] = {
            "mode": "store_and_forward",
            "note": (
                "Poor network simulated — alert queued locally and will sync "
                "via Internet when online. Bluetooth/LoRa hardware not required for demo."
            ),
        }
    payload["delivery"] = delivery
    _append_log(payload)
    return payload


def notify_sos_all_contacts(journey: Journey, alert: SosAlert) -> list[dict]:
    """Send SOS alert to every emergency contact saved for this user."""
    from app.models.contact import EmergencyContact as EC

    contacts = (
        EC.query.filter_by(user_id=journey.user_id)
        .order_by(EC.is_primary.desc(), EC.id.asc())
        .all()
    )
    if not contacts and journey.active_contact_id:
        fallback = EC.query.get(journey.active_contact_id)
        if fallback:
            contacts = [fallback]

    results: list[dict] = []
    for contact in contacts:
        try:
            results.append(notify_sos(journey, alert, contact))
        except Exception as err:  # noqa: BLE001 – never block other contacts
            results.append(
                {
                    "event": "sos_alert",
                    "contact_id": contact.id,
                    "contact_name": contact.name,
                    "contact_phone": contact.phone,
                    "delivery": {"status": "failed", "error": str(err)},
                }
            )
    return results


def _normalize_phone_e164_digits(phone: str) -> str:
    """Normalize phone number to international digits for Vonage API (e.g., 919901533228)."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("91") and len(digits) == 12:
        return digits
    if len(digits) == 10:
        return f"91{digits}"
    return digits


def _vonage_configured() -> bool:
    return bool(
        current_app.config.get("VONAGE_API_KEY")
        and current_app.config.get("VONAGE_API_SECRET")
    )


def _send_sms_vonage(to_phone: str, body: str) -> None:
    api_key = current_app.config["VONAGE_API_KEY"]
    api_secret = current_app.config["VONAGE_API_SECRET"]
    from_num = current_app.config.get("VONAGE_FROM_NUMBER") or "Vonage APIs"

    to_num = _normalize_phone_e164_digits(to_phone)
    url = "https://rest.nexmo.com/sms/json"
    payload = {
        "api_key": api_key,
        "api_secret": api_secret,
        "from": from_num,
        "to": to_num,
        "text": body,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_res = resp.read().decode("utf-8", errors="replace")
            res_data = json.loads(raw_res) if raw_res else {}
            current_app.logger.info("Vonage SMS API Response: %s", res_data)
            messages = res_data.get("messages") or []
            if messages and messages[0].get("status") != "0":
                err_text = messages[0].get("error-text", "Unknown Vonage error")
                raise RuntimeError(f"Vonage SMS error {messages[0].get('status')}: {err_text}")
    except urllib.error.HTTPError as err:

        detail = err.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"Vonage HTTP {err.code}: {detail}") from err


def _sms_text(payload: dict) -> str:
    """Compact SMS body."""
    if payload.get("event") == "sos_alert":
        traveler = payload.get("traveler") or "Traveler"
        reason = (payload.get("reason") or "emergency")[:100]
        share = payload.get("share_url") or ""
        loc = ""
        if payload.get("lat") is not None and payload.get("lng") is not None:
            loc = f" @ {payload['lat']:.4f},{payload['lng']:.4f}"
        return f"SOS! {traveler}: {reason}{loc}. Track: {share}"[:480]
    return (payload.get("message") or "")[:480]


def _deliver(payload: dict, contact: EmergencyContact | None) -> dict:
    """
    Attempt Vonage SMS delivery.
    Always attaches direct WhatsApp/SMS action URLs for 1-click fallback.
    """
    channels = ["in_app_log"]
    sms_ok = False
    sms_provider = None

    if contact and contact.phone:
        digits = re.sub(r"\D", "", contact.phone or "")
        int_phone = f"91{digits}" if len(digits) == 10 else digits
        msg_text = payload.get("message") or "EMERGENCY SOS ALERT"
        payload["whatsapp_url"] = f"https://wa.me/{int_phone}?text={urllib.parse.quote(msg_text)}"
        payload["sms_url"] = f"sms:{digits}?body={urllib.parse.quote(msg_text)}"

        if _vonage_configured() and payload.get("event") == "sos_alert":
            try:
                _send_sms_vonage(contact.phone, _sms_text(payload))
                channels.append("sms")
                sms_ok = True
                sms_provider = "vonage"
            except Exception as err:  # noqa: BLE001
                channels.append(f"sms_failed:vonage:{err}")
        elif _vonage_configured():
            channels.append("sms_skipped_journey_started")
        else:
            channels.append("sms_stub")

    network = "online"
    if current_app.config.get("SIMULATE_POOR_NETWORK"):
        network = "degraded"

    return {
        "status": "queued" if network == "degraded" else "recorded",
        "channels": channels,
        "sms_sent": sms_ok,
        "sms_provider": sms_provider,
        "network": network,
        "demo": not sms_ok,
    }



def _append_log(payload: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        current_app.logger.warning("Could not write notification log")
