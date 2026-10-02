"""
Application configuration loaded from environment variables.
Never hardcode secrets – use backend/.env
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env from the backend folder
load_dotenv()


class Config:
    """Base configuration for SafeRoute backend."""

    SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-dev-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "unsafe-jwt-key")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    # SQLAlchemy
    _db_url = os.getenv("DATABASE_URL", "sqlite:///saferoute.db")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CORS
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    # Safety / anomaly thresholds (Phases 8+)
    LOCATION_INTERVAL_SEC = int(os.getenv("LOCATION_INTERVAL_SEC", "5"))
    STOP_THRESHOLD_SEC = int(os.getenv("STOP_THRESHOLD_SEC", "150"))
    DEVIATION_THRESHOLD_M = int(os.getenv("DEVIATION_THRESHOLD_M", "100"))
    LOST_SIGNAL_SEC = int(os.getenv("LOST_SIGNAL_SEC", "75"))
    SAFETY_RESPONSE_SEC = int(os.getenv("SAFETY_RESPONSE_SEC", "40"))
    SOS_COUNTDOWN_SEC = int(os.getenv("SOS_COUNTDOWN_SEC", "20"))
    ANOMALY_COOLDOWN_SEC = int(os.getenv("ANOMALY_COOLDOWN_SEC", "180"))
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

    # Share / notify
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    SIMULATE_POOR_NETWORK = os.getenv("SIMULATE_POOR_NETWORK", "false").lower() == "true"

    # Mapbox Geocoding & Maps
    MAPBOX_ACCESS_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN", "")

    # Meta WhatsApp Cloud API (Automatic SOS & Emergency WhatsApp)
    WHATSAPP_CLOUD_API_TOKEN = os.getenv("WHATSAPP_CLOUD_API_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v21.0")
    WHATSAPP_TEMPLATE_NAME = os.getenv("WHATSAPP_TEMPLATE_NAME", "")
    WHATSAPP_TEMPLATE_LANG = os.getenv("WHATSAPP_TEMPLATE_LANG", "en_US")
    SEND_WHATSAPP_ON_JOURNEY_START = (
        os.getenv("SEND_WHATSAPP_ON_JOURNEY_START", "false").lower() == "true"
    )
