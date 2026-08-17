"""
Tests for user feedback collection and safety model retraining.
Run: python -m tests.test_feedback
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services.crime_data import score_route_lnglat
from app.services.feedback_service import retrain_model


def run():
    app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
        }
    )

    client = app.test_client()

    with app.app_context():
        # 1. Test GET empty feedback stats
        r = client.get("/api/feedback")
        assert r.status_code == 200
        data = r.get_json()
        assert data["stats"]["total_feedback_count"] == 0

        # 2. Test submitting positive user feedback
        r = client.post(
            "/api/feedback",
            json={
                "dest_label": "Acharya Institutes",
                "lat": 13.0837,
                "lng": 77.4857,
                "rating": 5,
                "safety_tags": ["well_lit", "safe_area"],
                "comments": "Very well lit street with good security presence.",
            },
        )
        assert r.status_code == 201
        res1 = r.get_json()
        assert res1["feedback"]["rating"] == 5
        assert "well_lit" in res1["feedback"]["safety_tags"]
        assert res1["stats"]["total_feedback_count"] == 1

        # 3. Test submitting negative user feedback (reporting hazards)
        r = client.post(
            "/api/feedback",
            json={
                "dest_label": "Dark Alley",
                "lat": 13.0850,
                "lng": 77.4830,
                "rating": 1,
                "safety_tags": ["poor_lighting", "isolated_street"],
                "comments": "Streetlights broken, dark isolated path.",
            },
        )
        assert r.status_code == 201

        # 4. Test explicit AI Model Retraining
        r = client.post("/api/feedback/retrain")
        assert r.status_code == 200
        retrain_res = r.get_json()
        assert retrain_res["metrics"]["status"] == "success"
        assert retrain_res["metrics"]["training_samples"] == 2
        assert retrain_res["metrics"]["model_accuracy_score"] > 0.85

        # 5. Verify dynamic route score adjustment
        safe_route_coords = [[77.4857, 13.0837], [77.4858, 13.0838]]
        unsafe_route_coords = [[77.4830, 13.0850], [77.4831, 13.0851]]

        score_safe = score_route_lnglat(safe_route_coords)["safety_score"]
        score_unsafe = score_route_lnglat(unsafe_route_coords)["safety_score"]

        assert score_safe > score_unsafe

        print("All User Feedback & Model Retraining tests passed cleanly.")


if __name__ == "__main__":
    run()
