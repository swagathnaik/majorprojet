"""
SafeRoute Flask app factory.
"""
from flask import Flask, jsonify
from app.config import Config
from app.extensions import db, jwt, cors


def create_app(config_class=Config, config_overrides=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    if config_overrides:
        app.config.update(config_overrides)

    # Extensions
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)

    # Import models so SQLAlchemy knows about them before create_all
    from app.models import user  # noqa: F401
    from app.models import contact  # noqa: F401
    from app.models import journey  # noqa: F401
    from app.models import location  # noqa: F401
    from app.models import anomaly  # noqa: F401
    from app.models import safety_check  # noqa: F401
    from app.models import sos  # noqa: F401

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.health import health_bp
    from app.routes.contacts import contacts_bp
    from app.routes.journeys import journeys_bp
    from app.routes.safety import safety_bp
    from app.routes.maps import maps_bp
    from app.routes.share import share_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(contacts_bp, url_prefix="/api/contacts")
    app.register_blueprint(journeys_bp, url_prefix="/api/journeys")
    app.register_blueprint(safety_bp, url_prefix="/api/safety-checks")
    app.register_blueprint(maps_bp, url_prefix="/api/maps")
    app.register_blueprint(share_bp, url_prefix="/api/share")

    # Create tables on startup (fine for SQLite MVP)
    with app.app_context():
        db.create_all()

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app
