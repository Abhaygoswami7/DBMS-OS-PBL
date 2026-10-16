"""
JWT Authentication Middleware & Role Guard Decorator
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/routes/auth_middleware.py
"""

from functools import wraps
from flask import request, jsonify, g
from backend.app.services.auth_service import auth_service

def get_bearer_token() -> str:
    """Extracts the Bearer token from the incoming request Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return ""

def token_required(allowed_roles=None):
    """
    Decorator to protect REST endpoints with JWT validation and role-based access control.
    - allowed_roles: Optional list of authorized roles (e.g. ['SUPER_ADMIN', 'CONSTITUENCY_OFFICER']).
    - If valid, injects current user payload into flask.g.current_user.
    - Returns 401 if token is missing or invalid.
    - Returns 403 if role is not permitted.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = get_bearer_token()
            if not token:
                return jsonify({
                    "error": "UNAUTHORIZED",
                    "message": "Authorization token required (Bearer <token>).",
                    "status_code": 401
                }), 401

            payload = auth_service.verify_token(token)
            if not payload:
                return jsonify({
                    "error": "UNAUTHORIZED",
                    "message": "Invalid, expired, or corrupted authentication token.",
                    "status_code": 401
                }), 401

            # Check role permissions if specified
            if allowed_roles:
                user_role = payload.get("role")
                if user_role not in allowed_roles:
                    return jsonify({
                        "error": "FORBIDDEN",
                        "message": f"Access forbidden. Required role in {allowed_roles}, but found '{user_role}'.",
                        "status_code": 403
                    }), 403

            g.current_user = payload
            return f(*args, **kwargs)
        return decorated
    return decorator
