"""
Flask Application Factory
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/__init__.py

Initializes Flask app with:
  - Flask-CORS configuration
  - Modular Blueprint registration
  - Uniform JSON error handlers (400, 401, 403, 404, 409, 500)
  - OS Concurrency Engine telemetry response headers
  - System health check endpoint (/api/health)
"""

import os
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app(test_config=None) -> Flask:
    """Creates and configures the Flask application instance."""
    app = Flask(__name__)

    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "smart-poll-flask-secret-2026"),
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "jwt-admin-secret-2026"),
        JSON_SORT_KEYS=False
    )

    if test_config:
        app.config.update(test_config)

    # Enable Cross-Origin Resource Sharing (CORS)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register Blueprints
    from backend.app.routes.auth_routes import auth_bp
    from backend.app.routes.voter_routes import voter_bp
    from backend.app.routes.booth_routes import booth_bp
    from backend.app.routes.allocation_routes import allocation_bp
    from backend.app.routes.admin_routes import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(voter_bp, url_prefix="/api")
    app.register_blueprint(booth_bp, url_prefix="/api")
    app.register_blueprint(allocation_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    # Health check endpoint
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "Smart Polling Booth Platform (One Nation One Election)",
            "version": "1.0.0",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "endpoints_ready": 12
        }), 200

    # -------------------------------------------------------------------------
    # Frontend Static File Serving
    # -------------------------------------------------------------------------
    from flask import send_from_directory
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

    @app.route("/", methods=["GET"])
    def serve_index():
        """Serves the voter portal homepage."""
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/admin", methods=["GET"])
    @app.route("/admin.html", methods=["GET"])
    def serve_admin():
        """Serves the administrative logistics & OS telemetry dashboard."""
        return send_from_directory(frontend_dir, "admin.html")

    @app.route("/css/<path:filename>", methods=["GET"])
    def serve_css(filename):
        """Serves CSS stylesheets."""
        return send_from_directory(os.path.join(frontend_dir, "css"), filename)

    @app.route("/js/<path:filename>", methods=["GET"])
    def serve_js(filename):
        """Serves JavaScript client files."""
        return send_from_directory(os.path.join(frontend_dir, "js"), filename)

    # OS Telemetry Response Headers
    @app.after_request
    def add_telemetry_headers(response):
        response.headers["X-Platform"] = "ONOE-Smart-Poll-2026"
        response.headers["X-OS-Concurrency-Engine"] = "Active"
        response.headers["X-Response-Timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return response

    # Uniform JSON Error Handlers
    @app.errorhandler(400)
    def bad_request(error):
        msg = error.description if hasattr(error, "description") else "Bad request parameters."
        return jsonify({
            "error": "BAD_REQUEST",
            "message": str(msg),
            "status_code": 400
        }), 400

    @app.errorhandler(401)
    def unauthorized(error):
        msg = error.description if hasattr(error, "description") else "Authentication required."
        return jsonify({
            "error": "UNAUTHORIZED",
            "message": str(msg),
            "status_code": 401
        }), 401

    @app.errorhandler(403)
    def forbidden(error):
        msg = error.description if hasattr(error, "description") else "Access forbidden."
        return jsonify({
            "error": "FORBIDDEN",
            "message": str(msg),
            "status_code": 403
        }), 403

    @app.errorhandler(404)
    def not_found(error):
        msg = error.description if hasattr(error, "description") else "Resource not found."
        return jsonify({
            "error": "NOT_FOUND",
            "message": str(msg),
            "status_code": 404
        }), 404

    @app.errorhandler(409)
    def conflict(error):
        msg = error.description if hasattr(error, "description") else "Resource conflict."
        return jsonify({
            "error": "CONFLICT",
            "message": str(msg),
            "status_code": 409
        }), 409

    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected server error occurred.",
            "status_code": 500
        }), 500

    return app
