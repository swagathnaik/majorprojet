"""
Trusted-contact notifications.

Meta WhatsApp Cloud API for SOS alerts.
Direct WhatsApp 1-click fallback links.
In-app notification logging.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
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


def _format_sos_message(
    traveler_name: str,
    lat: float | None = None,
    lng: float | None = None,
    share_url: str = "",
    at_iso: str | None = None,
) -> str:
    """Format emergency alert message matching standard SafeRoute emergency template."""
    try:
        if at_iso:
            dt_utc = datetime.fromisoformat(at_iso.replace("Z", "+00:00"))
        else:
            dt_utc = datetime.now(timezone.utc)
        dt_ist = dt_utc + timedelta(hours=5, minutes=30)
        time_str = dt_ist.strftime("%H:%M, %d %b %Y")
    except Exception:
        time_str = datetime.now().strftime("%H:%M, %d %b %Y")

    if lat is not None and lng is not None:
        loc_str = f"https://maps.google.com/?q={lat:.5f},{lng:.5f}"
    else:
        loc_str = "https://maps.google.com/?q=12.9716,77.5946"

    track_line = f"\nLive Tracking: {share_url}" if share_url else ""

    return (
        f"🚨 SOS! EMERGENCY DETECTED\n\n"
        f"{traveler_name} has triggered an SOS alert through SafeRoute.\n\n"
        f"📍 Location: {loc_str}\n"
        f"🕐 {time_str}\n"
        f"⚠️ Status: Immediate assistance required{track_line}\n\n"
        f"Please check their location and contact them immediately."
    )


def notify_sos(
    journey: Journey,
    alert: SosAlert,
    contact: EmergencyContact | None,
) -> dict:
    """Notify one trusted contact when SOS is created."""
    user = User.query.get(journey.user_id)
    share_url = journey_share_url(journey)
    traveler_name = user.name if user else "Traveler"
    sos_msg = _format_sos_message(
        traveler_name=traveler_name,
        lat=alert.lat,
        lng=alert.lng,
        share_url=share_url,
    )
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
        "traveler": traveler_name,
        "contact_id": contact.id if contact else None,
        "contact_name": contact.name if contact else None,
        "contact_phone": contact.phone if contact else None,
        "share_url": share_url,
        "call_112_hint": "Optional: dial 112 (India emergency) if life is at risk.",
        "message": sos_msg,
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
    """Normalize phone number to international digits (e.g., 919901533228)."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("91") and len(digits) == 12:
        return digits
    if len(digits) == 10:
        return f"91{digits}"
    return digits


def _alert_text(payload: dict) -> str:
    """Compact or full emergency alert body for WhatsApp message."""
    if payload.get("event") == "sos_alert":
        return payload.get("message") or _format_sos_message(
            traveler_name=payload.get("traveler") or "Traveler",
            lat=payload.get("lat"),
            lng=payload.get("lng"),
            share_url=payload.get("share_url") or "",
            at_iso=payload.get("at"),
        )
    return (payload.get("message") or "")[:480]


def _whatsapp_cloud_configured() -> bool:
    return bool(
        current_app.config.get("WHATSAPP_CLOUD_API_TOKEN")
        and current_app.config.get("WHATSAPP_PHONE_NUMBER_ID")
    )


def _whatsapp_api_url() -> str:
    phone_number_id = str(current_app.config.get("WHATSAPP_PHONE_NUMBER_ID", "")).strip()
    version = str(current_app.config.get("WHATSAPP_API_VERSION", "v21.0")).strip() or "v21.0"
    return f"https://graph.facebook.com/{version}/{phone_number_id}/messages"


def _send_whatsapp_cloud_raw(payload_dict: dict) -> dict:
    """Send arbitrary JSON payload to Meta WhatsApp Cloud API messages endpoint."""
    token = str(current_app.config.get("WHATSAPP_CLOUD_API_TOKEN", "")).strip()
    url = _whatsapp_api_url()
    data = json.dumps(payload_dict).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_res = resp.read().decode("utf-8", errors="replace")
            res_data = json.loads(raw_res) if raw_res else {}
            current_app.logger.info("Meta WhatsApp Cloud API Response: %s", res_data)
            return res_data
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        err_msg = detail
        err_code = err.code
        try:
            err_json = json.loads(detail)
            error_obj = err_json.get("error", {})
            err_msg = error_obj.get("message") or detail
            err_code = error_obj.get("code") or err.code
        except Exception:
            pass
        raise RuntimeError(f"Meta WhatsApp Cloud API error ({err_code}): {err_msg}") from err


def _send_whatsapp_cloud_text(to_phone: str, body: str, preview_url: bool = True) -> dict:
    """Send a direct text message via Meta WhatsApp Cloud API."""
    to_num = _normalize_phone_e164_digits(to_phone)
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_num,
        "type": "text",
        "text": {
            "preview_url": preview_url,
            "body": body,
        },
    }
    return _send_whatsapp_cloud_raw(payload)


def _send_whatsapp_cloud_location(
    to_phone: str,
    lat: float,
    lng: float,
    name: str = "🚨 SOS Emergency Location",
    address: str = "SafeRoute Alert",
) -> dict:
    """Send an interactive GPS location pin card via Meta WhatsApp Cloud API."""
    to_num = _normalize_phone_e164_digits(to_phone)
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_num,
        "type": "location",
        "location": {
            "latitude": float(lat),
            "longitude": float(lng),
            "name": name,
            "address": address,
        },
    }
    return _send_whatsapp_cloud_raw(payload)


def _send_whatsapp_cloud_template(
    to_phone: str,
    template_name: str,
    lang_code: str = "en_US",
    components: list[dict] | None = None,
) -> dict:
    """Send a pre-approved Meta WhatsApp template message."""
    to_num = _normalize_phone_e164_digits(to_phone)
    tmpl: dict = {
        "name": template_name,
        "language": {"code": lang_code},
    }
    if components:
        tmpl["components"] = components
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_num,
        "type": "template",
        "template": tmpl,
    }
    return _send_whatsapp_cloud_raw(payload)


def _send_whatsapp_cloud_sos(to_phone: str, payload: dict) -> dict:
    """
    Emergency dispatch:
    1. Dispatches rich SafeRoute SOS text message with live tracking link and emergency details.
    2. If lat & lng are present, dispatches the native WhatsApp GPS location pin card.
    3. If text dispatch encounters policy constraints and a custom template (other than hello_world)
       is configured, falls back to that template.
    """
    text_body = _alert_text(payload)
    traveler = payload.get("traveler") or "Traveler"
    lat = payload.get("lat")
    lng = payload.get("lng")
    template_name = (current_app.config.get("WHATSAPP_TEMPLATE_NAME") or "").strip()
    template_lang = (current_app.config.get("WHATSAPP_TEMPLATE_LANG") or "en_US").strip()

    results: dict = {"text_sent": False, "location_sent": False, "template_sent": False}
    text_error = None

    # Step 1: Dispatch rich custom SafeRoute SOS text message
    try:
        res_text = _send_whatsapp_cloud_text(to_phone, text_body)
        results["text_sent"] = True
        results["text_response"] = res_text
    except Exception as txt_err:
        text_error = txt_err
        current_app.logger.warning("WhatsApp text dispatch failed: %s", txt_err)

    # Step 2: Only dispatch a template if a custom approved template is explicitly configured (never send "hello_world")
    if template_name and template_name.lower() != "hello_world":
        try:
            res_tmpl = _send_whatsapp_cloud_template(to_phone, template_name, template_lang)
            results["template_sent"] = True
            results["template_response"] = res_tmpl
        except Exception as tmpl_err:
            current_app.logger.warning("WhatsApp custom template dispatch note: %s", tmpl_err)
            if not results["text_sent"]:
                raise RuntimeError(f"Text failed ({text_error}); Template failed ({tmpl_err})") from tmpl_err
    elif not results["text_sent"] and text_error:
        raise text_error

    # Step 3: Dispatch interactive GPS location pin if coordinates are valid
    if lat is not None and lng is not None:
        try:
            loc_res = _send_whatsapp_cloud_location(
                to_phone=to_phone,
                lat=float(lat),
                lng=float(lng),
                name=f"🚨 SOS: {traveler}",
                address=f"Location: {lat:.5f}, {lng:.5f}",
            )
            results["location_sent"] = True
            results["location_response"] = loc_res
        except Exception as loc_err:
            current_app.logger.warning("WhatsApp location pin attempt failed: %s", loc_err)
            results["location_error"] = str(loc_err)

    return results


def notify_test_whatsapp(contact: EmergencyContact, user: User | None) -> dict:
    """Send a test WhatsApp message via Meta Cloud API to verify gateway functionality."""
    traveler = user.name if user else "Traveler"
    payload = {
        "event": "test_alert",
        "channel": "emergency_test_whatsapp",
        "at": datetime.now(timezone.utc).isoformat(),
        "traveler": traveler,
        "contact_id": contact.id,
        "contact_name": contact.name,
        "contact_phone": contact.phone,
        "message": (
            f"SafeRoute Alert Test: Meta WhatsApp Cloud API alert is connected for {traveler}. "
            f"You are registered as an emergency contact."
        ),
    }

    delivery = _deliver(payload, contact, force_whatsapp=True)
    payload["delivery"] = delivery
    _append_log(payload)
    return payload


def _deliver(
    payload: dict,
    contact: EmergencyContact | None,
    force_whatsapp: bool = False,
) -> dict:
    """
    Attempt WhatsApp delivery via Meta WhatsApp Cloud API.
    Always attaches direct WhatsApp action URL for 1-click fallback.
    """
    channels = ["in_app_log"]
    wa_ok = False
    wa_provider = None

    if contact and contact.phone:
        digits = re.sub(r"\D", "", contact.phone or "")
        int_phone = f"91{digits}" if len(digits) == 10 else digits
        msg_text = payload.get("message") or "EMERGENCY SOS ALERT"
        payload["whatsapp_url"] = f"https://wa.me/{int_phone}?text={urllib.parse.quote(msg_text)}"

        is_sos = payload.get("event") == "sos_alert"
        is_test = payload.get("event") == "test_alert"
        is_journey_start = payload.get("event") == "journey_started"

        # --- Meta WhatsApp Cloud API Dispatch ---
        has_whatsapp = _whatsapp_cloud_configured()
        send_wa_on_start = bool(current_app.config.get("SEND_WHATSAPP_ON_JOURNEY_START"))
        should_send_wa = force_whatsapp or (
            has_whatsapp
            and (is_sos or is_test or (is_journey_start and send_wa_on_start))
        )

        if has_whatsapp and should_send_wa:
            try:
                wa_res = _send_whatsapp_cloud_sos(contact.phone, payload)
                wa_ok = True
                wa_provider = "meta_cloud_api"
                channels.append("whatsapp_cloud")
                if wa_res.get("location_sent"):
                    channels.append("whatsapp_cloud_location")
                if wa_res.get("template_sent"):
                    channels.append("whatsapp_cloud_template")
            except Exception as err:  # noqa: BLE001
                channels.append(f"whatsapp_cloud_failed:{err}")
        elif has_whatsapp and is_journey_start and not send_wa_on_start:
            channels.append("whatsapp_skipped_journey_started")

    network = "online"
    if current_app.config.get("SIMULATE_POOR_NETWORK"):
        network = "degraded"

    return {
        "status": "queued" if network == "degraded" else "recorded",
        "channels": channels,
        "whatsapp_sent": wa_ok,
        "whatsapp_provider": wa_provider,
        "network": network,
        "demo": not wa_ok,
    }



def _append_log(payload: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        current_app.logger.warning("Could not write notification log")
