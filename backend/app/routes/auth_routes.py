"""
Authentication REST API Routes
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/routes/auth_routes.py

Endpoints:
  - POST /api/auth/login: Authenticate demo admin or verified demo voter session; return JWT.
  - GET  /api/auth/captcha/generate: Generate random 6-character alphanumeric CAPTCHA challenge (Flask session).
  - POST /api/auth/captcha/validate: Validate user CAPTCHA answer case-insensitively and invalidate challenge.
"""

import random
import string
from flask import Blueprint, request, jsonify, session
from backend.app.services.auth_service import auth_service

auth_bp = Blueprint("auth_bp", __name__)

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    POST /api/auth/login
    Authenticates either:
      1. Administrative demo accounts (SUPER_ADMIN, CONSTITUENCY_OFFICER, BOOTH_OPERATOR, POLLING_OFFICER)
         Payload: {"username": "admin", "password": "admin2026password"}
      2. Verified demo voter sessions
         Payload: {"demo_epic_no": "DEM-UK-2026-0001"} or {"voter_id": 1}
    """
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")
    demo_epic_no = data.get("demo_epic_no")
    voter_id = data.get("voter_id")
    aadhaar_id = data.get("aadhaar_id")

    # 1. Admin login branch
    if username is not None or password is not None:
        if not username or not password:
            return jsonify({
                "error": "BAD_REQUEST",
                "message": "Both username and password are required for administrator login.",
                "status_code": 400
            }), 400

        auth_result = auth_service.authenticate_admin(username=username, password=password)
        if not auth_result:
            return jsonify({
                "error": "UNAUTHORIZED",
                "message": "Invalid administrator username or password.",
                "status_code": 401
            }), 401

        return jsonify({
            "success": True,
            "message": f"Administrator session authenticated for {auth_result['user']['name']}",
            **auth_result
        }), 200

    # 2. Voter session branch (synthetic Aadhaar ID or demo EPIC)
    if aadhaar_id:
        clean_aadhaar = "".join(filter(str.isdigit, str(aadhaar_id)))
        if len(clean_aadhaar) != 12:
            return jsonify({
                "error": "BAD_REQUEST",
                "message": "Aadhaar ID must be exactly 12 numeric digits (XXXX-XXXX-XXXX).",
                "status_code": 400
            }), 400
        last4 = int(clean_aadhaar[-4:]) if clean_aadhaar[-4:].isdigit() else 1
        v_idx = ((last4 - 1) % 60) + 1 if last4 > 0 else 1
        demo_epic_no = f"DEM-UK-2026-{v_idx:04d}"

    if demo_epic_no or voter_id:
        voter_result = auth_service.authenticate_voter_session(
            demo_epic_no=demo_epic_no,
            voter_id=voter_id
        )
        if not voter_result:
            return jsonify({
                "error": "NOT_FOUND",
                "message": f"Synthetic voter profile not found for identifier: {demo_epic_no or voter_id}",
                "status_code": 404
            }), 404

        return jsonify({
            "success": True,
            "message": f"Demo voter session authenticated for {voter_result['user']['name']}",
            **voter_result
        }), 200

    # Neither provided
    return jsonify({
        "error": "BAD_REQUEST",
        "message": "Missing credentials. Provide 'username' & 'password' for admin, or 'demo_epic_no' / 'voter_id' for voter session.",
        "status_code": 400
    }), 400


# -----------------------------------------------------------------------------
# CAPTCHA GENERATION & VALIDATION (Session-backed, case-insensitive)
# -----------------------------------------------------------------------------
@auth_bp.route("/captcha/generate", methods=["GET"])
def generate_captcha():
    """
    GET /api/auth/captcha/generate
    Generates a 6-character random alphanumeric CAPTCHA challenge
    (uppercase, lowercase, numbers) and stores its lowercase value in Flask session.
    """
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    captcha = "".join(random.choices(chars, k=6))
    session["captcha_answer"] = captcha.lower()
    return jsonify({
        "success": True,
        "captcha": captcha
    }), 200


@auth_bp.route("/captcha/validate", methods=["POST"])
def validate_captcha():
    """
    POST /api/auth/captcha/validate
    Validates user submitted CAPTCHA against Flask session (case-insensitive).
    Invalidates the challenge after check to prevent replay.
    """
    data = request.get_json(silent=True) or {}
    user_answer = str(data.get("answer", "")).strip().lower()
    expected = session.get("captcha_answer", "")

    if not expected or not user_answer or user_answer != expected:
        session.pop("captcha_answer", None)
        return jsonify({
            "valid": False,
            "error": "Invalid or expired CAPTCHA. Please refresh and try again."
        }), 400

    session.pop("captcha_answer", None)
    return jsonify({
        "valid": True,
        "message": "CAPTCHA verification successful."
    }), 200

