"""
Trusted-contact notifications (Phase 10–12).

Demo mode: records notification events (no real SMS gateway required).
Optional SMTP if NOTIFY_SMTP_* env vars are set.
Optional Fast2SMS (India) if FAST2SMS_API_KEY is set.
Optional Twilio SMS if TWILIO_* env vars are set.
"""
from __future__ import annotations

import base64
import json
import re
import smtplib
import urllib.error
import urllib.parse
import urllib.request
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


def _normalize_phone_e164(phone: str) -> str:
    """Normalize Indian/local numbers to E.164 (+91...) for SMS gateways."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return phone
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    if phone.strip().startswith("+"):
        return phone.strip()
    return f"+{digits}"


def _normalize_phone_india_10(phone: str) -> str:
    """Extract a 10-digit Indian mobile number for Fast2SMS."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("91") and len(digits) >= 12:
        digits = digits[-10:]
    elif len(digits) > 10:
        digits = digits[-10:]
    if len(digits) != 10:
        raise ValueError(f"Invalid Indian mobile number: {phone}")
    return digits


def _sms_text(payload: dict) -> str:
    """Compact SMS body (Fast2SMS / Twilio character limits)."""
    if payload.get("event") == "sos_alert":
        traveler = payload.get("traveler") or "Traveler"
        reason = (payload.get("reason") or "emergency")[:100]
        share = payload.get("share_url") or ""
        loc = ""
        if payload.get("lat") is not None and payload.get("lng") is not None:
            loc = f" @ {payload['lat']:.4f},{payload['lng']:.4f}"
        return f"SOS! {traveler}: {reason}{loc}. Track: {share}"[:480]
    return (payload.get("message") or "")[:480]


def _fast2sms_configured() -> bool:
    return bool(current_app.config.get("FAST2SMS_API_KEY"))


def _send_sms_fast2sms(to_phone: str, body: str) -> None:
    api_key = current_app.config["FAST2SMS_API_KEY"]
    numbers = _normalize_phone_india_10(to_phone)
    url = "https://www.fast2sms.com/dev/bulkV2"
    data = urllib.parse.urlencode(
        {
            "message": body,
            "route": "q",
            "language": "english",
            "numbers": numbers,
        }
    ).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("authorization", api_key)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"Fast2SMS HTTP {err.code}: {detail}") from err

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Fast2SMS invalid response: {raw[:200]}") from err

    if not result.get("return"):
        msg = result.get("message")
        if isinstance(msg, list):
            msg = ", ".join(str(m) for m in msg)
        raise RuntimeError(f"Fast2SMS: {msg or 'send failed'}")


def _twilio_configured() -> bool:
    return bool(
        current_app.config.get("TWILIO_ACCOUNT_SID")
        and current_app.config.get("TWILIO_AUTH_TOKEN")
        and current_app.config.get("TWILIO_FROM_NUMBER")
    )


def _send_sms_twilio(to_phone: str, body: str) -> None:
    sid = current_app.config["TWILIO_ACCOUNT_SID"]
    token = current_app.config["TWILIO_AUTH_TOKEN"]
    from_num = current_app.config["TWILIO_FROM_NUMBER"]
    to_e164 = _normalize_phone_e164(to_phone)

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urllib.parse.urlencode(
        {"To": to_e164, "From": from_num, "Body": body}
    ).encode()
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"Twilio HTTP {resp.status}")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"Twilio error {err.code}: {detail}") from err


def _deliver(payload: dict, contact: EmergencyContact | None) -> dict:
    """Attempt SMS (Twilio) + SMTP if configured; always record a demo receipt."""
    channels = ["in_app_log"]
    smtp_ok = False
    sms_ok = False
    sms_provider = None

    if contact and contact.phone:
        if _fast2sms_configured():
            try:
                _send_sms_fast2sms(contact.phone, _sms_text(payload))
                channels.append("sms")
                sms_ok = True
                sms_provider = "fast2sms"
            except Exception as err:  # noqa: BLE001 – demo resilient
                channels.append(f"sms_failed:fast2sms:{err}")
        elif _twilio_configured():
            try:
                _send_sms_twilio(contact.phone, _sms_text(payload))
                channels.append("sms")
                sms_ok = True
                sms_provider = "twilio"
            except Exception as err:  # noqa: BLE001 – demo resilient
                channels.append(f"sms_failed:twilio:{err}")
        else:
            channels.append("sms_stub")

    contact_email = getattr(contact, "email", None) if contact else None
    smtp_to = contact_email or current_app.config.get("NOTIFY_EMAIL_TO") or ""
    if current_app.config.get("NOTIFY_SMTP_HOST") and smtp_to:
        try:
            subject = "🚨 EMERGENCY SOS ALERT - SafeRoute" if payload.get("event") == "sos_alert" else f"SafeRoute: {payload.get('traveler')} shared a journey"
            _send_smtp(smtp_to, subject, payload["message"], html_body=_build_html_email(payload))
            channels.append("email")
            smtp_ok = True
        except Exception as err:  # noqa: BLE001 – demo resilient
            channels.append(f"email_failed:{err}")

    network = "online"
    if current_app.config.get("SIMULATE_POOR_NETWORK"):
        network = "degraded"

    return {
        "status": "queued" if network == "degraded" else "recorded",
        "channels": channels,
        "sms_sent": sms_ok,
        "sms_provider": sms_provider,
        "smtp_sent": smtp_ok,
        "network": network,
        "demo": not sms_ok and not smtp_ok,
    }


def _build_html_email(payload: dict) -> str:
    """Generate HTML email body for emergency alerts and journey notifications."""
    traveler = payload.get("traveler") or "Traveler"
    share_url = payload.get("share_url") or "#"
    event = payload.get("event")

    if event == "sos_alert":
        reason = payload.get("reason") or "Emergency alert triggered"
        loc = f"{payload['lat']:.5f}, {payload['lng']:.5f}" if payload.get("lat") is not None and payload.get("lng") is not None else "Location updating..."
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 2px solid #e53e3e; border-radius: 8px; background-color: #fff5f5;">
            <h2 style="color: #c53030; margin-top: 0;">🚨 EMERGENCY SOS ALERT</h2>
            <p style="font-size: 16px; color: #2d3748;">
                <strong>{traveler}</strong> has triggered an emergency SOS alert on SafeRoute!
            </p>
            <div style="background-color: #ffffff; padding: 15px; border-radius: 6px; border: 1px solid #feb2b2; margin: 15px 0;">
                <p style="margin: 5px 0;"><strong>Reason:</strong> {reason}</p>
                <p style="margin: 5px 0;"><strong>Current Coordinates:</strong> {loc}</p>
                <p style="margin: 5px 0;"><strong>Time:</strong> {payload.get('at', '')}</p>
            </div>
            <div style="text-align: center; margin: 25px 0;">
                <a href="{share_url}" style="background-color: #e53e3e; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px; display: inline-block;">
                    📍 TRACK LIVE LOCATION NOW
                </a>
            </div>
            <p style="font-size: 12px; color: #718096; text-align: center;">
                SafeRoute Personal Journey Safety System
            </p>
        </div>
        """
    
    dest = payload.get("destination") or "their destination"
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f7fafc;">
        <h2 style="color: #2b6cb0; margin-top: 0;">🗺️ Safe Journey Started</h2>
        <p style="font-size: 16px; color: #2d3748;">
            <strong>{traveler}</strong> has started a Safe Journey to <strong>{dest}</strong>.
        </p>
        <div style="text-align: center; margin: 25px 0;">
            <a href="{share_url}" style="background-color: #3182ce; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                View Live Journey Map
            </a>
        </div>
    </div>
    """


def _send_smtp(to_addr: str, subject: str, body: str, html_body: str | None = None) -> None:
    host = current_app.config["NOTIFY_SMTP_HOST"]
    port = int(current_app.config.get("NOTIFY_SMTP_PORT", 587))
    user = current_app.config.get("NOTIFY_SMTP_USER") or ""
    password = current_app.config.get("NOTIFY_SMTP_PASSWORD") or ""
    from_addr = current_app.config.get("NOTIFY_SMTP_FROM") or user or "saferoute@localhost"

    msg = EmailMessage()
    msg["Subject"] = subject if subject.startswith("[SafeRoute]") else f"[SafeRoute] {subject}"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

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
