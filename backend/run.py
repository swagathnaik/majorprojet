"""
SafeRoute Flask application entry point.
Run: python run.py
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # host=0.0.0.0 allows access from phone on same Wi-Fi during GPS demos
    app.run(host="0.0.0.0", port=5000, debug=True)
