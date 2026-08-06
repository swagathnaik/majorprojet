"""
Trusted-contact notifications (Phase 10–12).

Demo mode: records notification events (no real SMS gateway required).
Optional SMTP if NOTIFY_SMTP_* env vars are set.
"""
from __future__ import annotations

import json
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
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
    """Notify trusted contact (+ optional 112 hint) when SOS is created."""
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
    # Simulate offline / poor-network fallback path for demos
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


def _deliver(payload: dict, contact: EmergencyContact | None) -> dict:
    """Attempt SMTP if configured; always record a demo delivery receipt."""
    channels = ["in_app_log"]
    smtp_ok = False
    smtp_to = current_app.config.get("NOTIFY_EMAIL_TO") or ""
    if current_app.config.get("NOTIFY_SMTP_HOST") and smtp_to:
        try:
            _send_smtp(smtp_to, payload.get("event", "SafeRoute"), payload["message"])
            channels.append("email")
            smtp_ok = True
        except Exception as err:  # noqa: BLE001 – demo resilient
            channels.append(f"email_failed:{err}")

    # Demo SMS stub (no Twilio key needed)
    if contact and contact.phone:
        channels.append("sms_stub")

    network = "online"
    if current_app.config.get("SIMULATE_POOR_NETWORK"):
        network = "degraded"

    return {
        "status": "queued" if network == "degraded" else "recorded",
        "channels": channels,
        "smtp_sent": smtp_ok,
        "network": network,
        "demo": True,
    }


def _send_smtp(to_addr: str, subject: str, body: str) -> None:
    host = current_app.config["NOTIFY_SMTP_HOST"]
    port = int(current_app.config.get("NOTIFY_SMTP_PORT", 587))
    user = current_app.config.get("NOTIFY_SMTP_USER") or ""
    password = current_app.config.get("NOTIFY_SMTP_PASSWORD") or ""
    from_addr = current_app.config.get("NOTIFY_SMTP_FROM") or user or "saferoute@localhost"

    msg = EmailMessage()
    msg["Subject"] = f"[SafeRoute] {subject}"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=12) as smtp:
        smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.send_message(msg)


def _append_log(payload: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        current_app.logger.warning("Could not write notification log")
