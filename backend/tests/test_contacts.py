"""
Phase 3 – emergency contact CRUD tests.
Run: python -m tests.test_contacts
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def run():
    app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
        }
    )

    with app.app_context():
        client = app.test_client()

        # Register user
        r = client.post(
            "/api/auth/register",
            json={
                "name": "Bob",
                "email": "bob@example.com",
                "password": "secret1",
            },
        )
        assert r.status_code == 201, r.data
        token = r.get_json()["access_token"]
        headers = auth_header(token)

        # Empty list
        r = client.get("/api/contacts", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["contacts"] == []

        # Create first contact → auto primary
        r = client.post(
            "/api/contacts",
            headers=headers,
            json={
                "name": "Mom",
                "phone": "9876543210",
                "relationship": "Mother",
            },
        )
        assert r.status_code == 201, r.data
        mom = r.get_json()["contact"]
        assert mom["is_primary"] is True
        mom_id = mom["id"]

        # Create second contact
        r = client.post(
            "/api/contacts",
            headers=headers,
            json={
                "name": "Best Friend",
                "phone": "9123456780",
                "relationship": "Friend",
                "is_primary": True,
            },
        )
        assert r.status_code == 201, r.data
        friend = r.get_json()["contact"]
        assert friend["is_primary"] is True
        friend_id = friend["id"]

        # Mom should no longer be primary
        r = client.get(f"/api/contacts/{mom_id}", headers=headers)
        assert r.get_json()["contact"]["is_primary"] is False

        # Update
        r = client.put(
            f"/api/contacts/{mom_id}",
            headers=headers,
            json={"name": "Mother", "phone": "9876543211"},
        )
        assert r.status_code == 200
        assert r.get_json()["contact"]["name"] == "Mother"

        # Set primary back to mom
        r = client.patch(f"/api/contacts/{mom_id}/primary", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["contact"]["is_primary"] is True

        r = client.get(f"/api/contacts/{friend_id}", headers=headers)
        assert r.get_json()["contact"]["is_primary"] is False

        # List ordered with primary first
        r = client.get("/api/contacts", headers=headers)
        contacts = r.get_json()["contacts"]
        assert len(contacts) == 2
        assert contacts[0]["id"] == mom_id

        # Invalid phone
        r = client.post(
            "/api/contacts",
            headers=headers,
            json={"name": "X", "phone": "12", "relationship": "Other"},
        )
        assert r.status_code == 400

        # Delete primary → promote remaining
        r = client.delete(f"/api/contacts/{mom_id}", headers=headers)
        assert r.status_code == 200
        r = client.get("/api/contacts", headers=headers)
        remaining = r.get_json()["contacts"]
        assert len(remaining) == 1
        assert remaining[0]["id"] == friend_id
        assert remaining[0]["is_primary"] is True

        # Unauthorized without token
        r = client.get("/api/contacts")
        assert r.status_code == 401

        print("All Phase 3 contact tests passed.")


if __name__ == "__main__":
    run()
