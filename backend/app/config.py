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
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///saferoute.db")
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

    # Share / notify (Phase 10–12)
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    SIMULATE_POOR_NETWORK = os.getenv("SIMULATE_POOR_NETWORK", "false").lower() == "true"
    NOTIFY_SMTP_HOST = os.getenv("NOTIFY_SMTP_HOST", "")
    NOTIFY_SMTP_PORT = int(os.getenv("NOTIFY_SMTP_PORT", "587"))
    NOTIFY_SMTP_USER = os.getenv("NOTIFY_SMTP_USER", "")
    NOTIFY_SMTP_PASSWORD = os.getenv("NOTIFY_SMTP_PASSWORD", "")
    NOTIFY_SMTP_FROM = os.getenv("NOTIFY_SMTP_FROM", "")
    NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "")

    # Vonage SMS to emergency contact phone numbers
    VONAGE_API_KEY = os.getenv("VONAGE_API_KEY", "")
    VONAGE_API_SECRET = os.getenv("VONAGE_API_SECRET", "")
    VONAGE_FROM_NUMBER = os.getenv("VONAGE_FROM_NUMBER", "Vonage APIs")

    # Free instant notification push alternatives (Telegram, Discord, Webhooks)

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
    NOTIFY_WEBHOOK_URL = os.getenv("NOTIFY_WEBHOOK_URL", "")

