"""
Simple Phase 2 auth smoke tests.
Run from backend/ with venv active:
  python -m tests.test_auth
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models.user import User


def run():
    app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
        }
    )

    with app.app_context():
        client = app.test_client()

        # Health
        r = client.get("/api/health")
        assert r.status_code == 200, r.data
        assert r.get_json()["status"] == "ok"

        # Register
        r = client.post(
            "/api/auth/register",
            json={
                "name": "Alice",
                "email": "alice@example.com",
                "phone": "9000000000",
                "password": "secret1",
            },
        )
        assert r.status_code == 201, r.data
        data = r.get_json()
        assert "access_token" in data
        token = data["access_token"]

        # Duplicate email
        r = client.post(
            "/api/auth/register",
            json={
                "name": "Alice",
                "email": "alice@example.com",
                "password": "secret1",
            },
        )
        assert r.status_code == 409

        # Login
        r = client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "secret1"},
        )
        assert r.status_code == 200, r.data

        # Bad login
        r = client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "nope"},
        )
        assert r.status_code == 401

        # Me
        r = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.data
        assert r.get_json()["user"]["email"] == "alice@example.com"

        # Password not stored plain
        user = User.query.filter_by(email="alice@example.com").first()
        assert user.password_hash != "secret1"
        assert user.check_password("secret1")

        print("All Phase 2 auth tests passed.")


if __name__ == "__main__":
    run()
