"""
Trusted-contact notifications (Phase 10–12).

Demo mode: records notification events (no real SMS gateway required).
Optional SMTP if NOTIFY_SMTP_* env vars are set.
Optional Vonage SMS if VONAGE_* env vars are set.
"""
from __future__ import annotations

import json
import re
import smtplib
import ssl
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
    Attempt multi-gateway delivery:
      SMS: Vonage SMS
      Push/Bot: Telegram -> Discord -> Custom Webhook
      Email: SMTP
    Always attaches direct WhatsApp/SMS action URLs for 1-click fallback.
    """
    channels = ["in_app_log"]
    smtp_ok = False
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



    # Free instant notification alternatives: Telegram Bot & Discord Webhook
    tg_token = current_app.config.get("TELEGRAM_BOT_TOKEN")
    tg_chat = current_app.config.get("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat:
        try:
            _send_telegram(tg_token, tg_chat, payload.get("message", ""))
            channels.append("telegram")
        except Exception as err:  # noqa: BLE001
            channels.append(f"telegram_failed:{err}")

    discord_url = current_app.config.get("DISCORD_WEBHOOK_URL")
    if discord_url:
        try:
            _send_discord(discord_url, payload.get("message", ""))
            channels.append("discord")
        except Exception as err:  # noqa: BLE001
            channels.append(f"discord_failed:{err}")

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

    webhook_url = current_app.config.get("NOTIFY_WEBHOOK_URL")
    if webhook_url:
        try:
            _send_webhook(webhook_url, payload)
            channels.append("webhook")
        except Exception as err:  # noqa: BLE001
            channels.append(f"webhook_failed:{err}")

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


def _send_telegram(token: str, chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"Telegram HTTP {resp.status}")


def _send_discord(url: str, message: str) -> None:
    data = json.dumps({"content": message}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"Discord HTTP {resp.status}")


def _ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        return ssl.create_default_context()
    except Exception:
        return ssl._create_unverified_context()


def _send_webhook(url: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "SafeRoute-SOS-Notifier/1.0")

    ctx = _ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"Webhook HTTP {resp.status}")
    except urllib.error.URLError as err:
        if "CERTIFICATE_VERIFY_FAILED" in str(err):
            unverified_ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=12, context=unverified_ctx) as resp:
                if resp.status >= 400:
                    raise RuntimeError(f"Webhook HTTP {resp.status}")
        else:
            raise




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
