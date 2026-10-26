"""
Voter Registration and Simulated Verification REST API Routes
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/routes/voter_routes.py

Endpoints:
  - POST /api/voters/register: Register a new synthetic demo voter or look up existing voter.
  - POST /api/verification/mock: Simulated ECI identity verification with explicit consent check.
"""

import re
import datetime
from flask import Blueprint, request, jsonify
from backend.app.services.voter_service import voter_service
from backend.app.services.auth_service import auth_service
from backend.app.services.booth_service import booth_service
from backend.app.services.verification_service import verification_service

voter_bp = Blueprint("voter_bp", __name__)

FORBIDDEN_REAL_KEYWORDS = ["aadhaar", "pan", "passport", "fingerprint", "iris", "biometric_raw"]

@voter_bp.route("/voters/register", methods=["POST"])
def register_or_lookup_voter():
    """
    POST /api/voters/register
    Registers a new synthetic demo voter (DEM-UK-2026-XXXX) or looks up an existing voter.
    Validates:
      - Age >= 18 (computed from DOB)
      - Synthetic EPIC format (DEM-UK-2026-XXXX)
      - Constituency / polling booth assignment
    """
    data = request.get_json(silent=True) or {}
    demo_epic_no = data.get("demo_epic_no", "").strip().upper()
    action = data.get("action", "").lower()

    if not demo_epic_no:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Missing 'demo_epic_no' in request body.",
            "status_code": 400
        }), 400

    # Strict synthetic identifier regex validation
    if not voter_service.SYNTHETIC_EPIC_PATTERN.match(demo_epic_no):
        return jsonify({
            "error": "INVALID_EPIC_FORMAT",
            "message": f"EPIC number '{demo_epic_no}' violates synthetic standard. Must match 'DEM-UK-2026-XXXX'.",
            "status_code": 400
        }), 400

    existing_voter = voter_service.get_voter_by_demo_epic(demo_epic_no)

    # If action is lookup OR the voter already exists and we didn't specify force create
    if action == "lookup" or (existing_voter and "full_name" not in data):
        if existing_voter:
            return jsonify({
                "success": True,
                "status": "EXISTING_VOTER",
                "message": f"Voter profile retrieved for {demo_epic_no}",
                "voter": existing_voter
            }), 200
        else:
            return jsonify({
                "error": "NOT_FOUND",
                "message": f"Synthetic voter '{demo_epic_no}' not found in registry.",
                "status_code": 404
            }), 404

    # If voter already exists, return existing profile with 200 OK
    if existing_voter:
        return jsonify({
            "success": True,
            "status": "EXISTING_VOTER",
            "message": f"Voter '{demo_epic_no}' is already registered.",
            "voter": existing_voter
        }), 200

    # New Registration flow: Validate required fields
    full_name = data.get("full_name")
    dob_str = data.get("dob")
    gender = data.get("gender")
    assigned_booth_id = data.get("assigned_booth_id")

    if not full_name or not dob_str or not gender or not assigned_booth_id:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Required fields for registration: 'full_name', 'dob' (YYYY-MM-DD), 'gender', 'assigned_booth_id'.",
            "status_code": 400
        }), 400

    # Age validation (age >= 18)
    try:
        dob_date = datetime.date.fromisoformat(str(dob_str))
    except ValueError:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Invalid DOB format. Expected ISO-8601 YYYY-MM-DD.",
            "status_code": 400
        }), 400

    today = datetime.date.today()
    age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
    if age < 18:
        return jsonify({
            "error": "UNDERAGE_VOTER",
            "message": f"Voter is {age} years old. Must be at least 18 years of age to register.",
            "status_code": 400
        }), 400

    # Validate booth assignment exists
    booths = booth_service.get_polling_booths()
    valid_booth_ids = {b["booth_id"] for b in booths}
    if int(assigned_booth_id) not in valid_booth_ids:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": f"Invalid booth_id {assigned_booth_id}. Must be one of seeded polling booths {sorted(list(valid_booth_ids))}.",
            "status_code": 400
        }), 400

    # Optional Identification number validation before registration (Never store raw digits)
    raw_id = data.get("identification_number") or data.get("id_number")
    anonymized_hash = None
    if raw_id:
        is_valid, err_code, err_msg = verification_service.validate_raw_identifier(raw_id)
        if not is_valid:
            return jsonify({
                "error": err_code,
                "message": f"Identification validation failed: {err_msg}",
                "status_code": 400
            }), 400
        anonymized_hash = verification_service.hash_identifier(raw_id)

    # Perform registration
    success, reason, new_voter_id = voter_service.register_synthetic_voter(data)
    if not success:
        return jsonify({
            "error": "REGISTRATION_FAILED",
            "message": reason,
            "status_code": 400
        }), 400

    # If identification was supplied, record only the 64-character anonymized hash token in simulated_verifications
    if anonymized_hash and new_voter_id:
        try:
            from database.db_pool import db_pool
            with db_pool.get_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    INSERT INTO simulated_verifications
                    (voter_id, booth_id, simulated_token, verification_method, status)
                    VALUES (%s, %s, %s, 'SIMULATED_EPIC_HASH', 'PASSED');
                    """,
                    (new_voter_id, int(assigned_booth_id), anonymized_hash)
                )
                conn.commit()
        except Exception as e:
            pass

    created_voter = voter_service.get_voter_by_id(new_voter_id)
    return jsonify({
        "success": True,
        "status": "REGISTERED",
        "message": f"Synthetic demo voter registered successfully with ID {new_voter_id}.",
        "voter": created_voter,
        "anonymized_hash": anonymized_hash
    }), 201


@voter_bp.route("/verification/mock", methods=["POST"])
def simulated_verification():
    """
    POST /api/verification/mock
    Simulated ECI identity verification with explicit consent_given=true check.
    Validates format pre-hashing and computes 64-character anonymized token.
    Never accepts real government IDs or raw biometrics.
    """
    data = request.get_json(silent=True) or {}

    # 1. Guardrail Check: Real IDs / Raw Biometrics Forbidden
    serialized_str = str(data).lower()
    for kw in FORBIDDEN_REAL_KEYWORDS:
        if kw in serialized_str:
            return jsonify({
                "error": "REAL_CREDENTIALS_REJECTED",
                "message": "Real citizen government IDs or biometrics are strictly forbidden. Only synthetic demo tokens are permitted.",
                "status_code": 400
            }), 400

    # 2. Guardrail Check: Explicit Consent Mandatory
    consent_given = data.get("consent_given")
    if consent_given is not True:
        return jsonify({
            "error": "CONSENT_REQUIRED",
            "message": "Explicit citizen consent (consent_given=true) is mandatory for simulated ECI verification.",
            "status_code": 400
        }), 400

    # 3. Resolve Voter Identifier
    voter_id = data.get("voter_id")
    demo_epic_no = data.get("demo_epic_no")
    booth_id = data.get("booth_id")

    if not voter_id and demo_epic_no:
        voter = voter_service.get_voter_by_demo_epic(demo_epic_no)
        if voter:
            voter_id = voter["voter_id"]

    if not voter_id or not booth_id:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Both 'voter_id' (or 'demo_epic_no') and 'booth_id' are required.",
            "status_code": 400
        }), 400

    method = data.get("verification_method", "SIMULATED_OTP").upper()
    mock_input = data.get("mock_input") or data.get("identification_number") or data.get("id_number")

    # Pre-hashing format validation on raw input (clean rejection without storing)
    if mock_input and not str(mock_input).startswith("SIM-OTP-"):
        is_valid, err_code, err_msg = verification_service.validate_raw_identifier(mock_input)
        if not is_valid:
            return jsonify({
                "error": err_code,
                "message": f"Identification format invalid: {err_msg}",
                "status_code": 400
            }), 400

    success, status_code, token = auth_service.verify_simulated_voter(
        voter_id=int(voter_id),
        booth_id=int(booth_id),
        method=method,
        mock_input=mock_input
    )

    if not success:
        if status_code == "VOTER_NOT_FOUND":
            return jsonify({
                "error": "NOT_FOUND",
                "message": f"Voter ID {voter_id} not found in synthetic registry.",
                "status_code": 404
            }), 404
        elif status_code == "INVALID_BOOTH_JURISDICTION":
            return jsonify({
                "error": "INVALID_BOOTH_JURISDICTION",
                "message": f"Voter ID {voter_id} is not registered in polling booth {booth_id}.",
                "status_code": 400
            }), 400
        else:
            return jsonify({
                "error": status_code,
                "message": f"Simulated verification failed: {status_code}",
                "status_code": 400
            }), 400

    return jsonify({
        "success": True,
        "status": "PASSED",
        "verification_method": method,
        "simulated_token": token,
        "voter_id": int(voter_id),
        "booth_id": int(booth_id),
        "guardrail_compliance": {
            "is_synthetic": True,
            "disclaimer": "Simulated synthetic verification only. Zero real citizen credentials processed."
        }
    }), 200
