"""
Authentication & Simulated Identity Verification Service
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Handles:
  1. Administrative JWT token issuance, decoding, and role validation.
  2. Synthetic Voter Simulated Verification (Mock OTP, Mock EPIC Hash, Mock Biometric Token).

STRICT PRIVACY GUARDRAILS:
Zero real citizen credentials, zero real Aadhaar/biometric data. Synthetic tokens only.
"""

import os
import time
import random
import jwt
import logging
from typing import Dict, Any, Optional, Tuple
from database.db_pool import db_pool
from backend.app.os_engine.memory_and_logger import os_file_logger

logger = logging.getLogger("auth_service")

# Predefined synthetic demo credentials for evaluation/demonstration
DEMO_ADMIN_CREDENTIALS = {
    "admin": {
        "password": "admin2026password",
        "role": "SUPER_ADMIN",
        "name": "State Election Logistics Officer"
    },
    "constituency_officer": {
        "password": "officer2026password",
        "role": "CONSTITUENCY_OFFICER",
        "name": "District Returning Officer"
    },
    "booth_operator": {
        "password": "operator2026password",
        "role": "BOOTH_OPERATOR",
        "name": "Booth Level Polling Operator"
    },
    "officer_ddn": {
        "password": "officer2026password",
        "role": "POLLING_OFFICER",
        "name": "Dehradun Station Supervisor"
    },
    "officer_hwr": {
        "password": "officer2026password",
        "role": "POLLING_OFFICER",
        "name": "Haridwar Station Supervisor"
    }
}

class AuthService:
    """Service providing JWT admin auth and simulated voter verification."""
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY", "jwt-admin-secret-2026-secure-key-32b")
        self.algorithm = "HS256"
        self.token_expiry_seconds = 86400  # 24 Hours

    # -------------------------------------------------------------------------
    # 1. ADMIN JWT AUTHENTICATION
    # -------------------------------------------------------------------------
    def authenticate_admin(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Validates administrator credentials and issues a signed JWT token."""
        user = DEMO_ADMIN_CREDENTIALS.get(username)
        if not user or user["password"] != password:
            return None

        now = int(time.time())
        payload = {
            "sub": username,
            "role": user["role"],
            "name": user["name"],
            "iat": now,
            "exp": now + self.token_expiry_seconds
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.token_expiry_seconds,
            "user": {
                "username": username,
                "role": user["role"],
                "name": user["name"]
            }
        }

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verifies and decodes a JWT token. Returns payload dict or None if invalid/expired."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
            logger.warning("JWT verification failed: %s", e)
            return None

    def has_role(self, token_payload: Dict[str, Any], allowed_roles: list) -> bool:
        """Checks if the user role in JWT payload belongs to allowed_roles."""
        return token_payload.get("role") in allowed_roles

    def authenticate_voter_session(
        self,
        demo_epic_no: Optional[str] = None,
        voter_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Issues a verified demo voter session JWT token."""
        from backend.app.services.voter_service import voter_service
        voter = None
        if demo_epic_no:
            voter = voter_service.get_voter_by_demo_epic(demo_epic_no)
        elif voter_id:
            voter = voter_service.get_voter_by_id(voter_id)

        if not voter:
            return None

        now = int(time.time())
        payload = {
            "sub": voter["demo_epic_no"],
            "voter_id": voter["voter_id"],
            "role": "VOTER",
            "name": voter["full_name"],
            "booth_id": voter.get("assigned_booth_id"),
            "iat": now,
            "exp": now + self.token_expiry_seconds
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.token_expiry_seconds,
            "user": {
                "voter_id": voter["voter_id"],
                "demo_epic_no": voter["demo_epic_no"],
                "role": "VOTER",
                "name": voter["full_name"],
                "assigned_booth_id": voter.get("assigned_booth_id")
            }
        }

    # -------------------------------------------------------------------------
    # 2. SIMULATED SYNTHETIC VOTER AUTHENTICATION
    # -------------------------------------------------------------------------
    def generate_simulated_otp(self, voter_id: int) -> str:
        """Generates a synthetic mock 6-digit OTP for testing."""
        return f"SIM-OTP-{random.randint(100000, 999999)}"

    def verify_simulated_voter(
        self,
        voter_id: int,
        booth_id: int,
        method: str = "SIMULATED_OTP",
        mock_input: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Simulates voter identity verification (guardrail compliant):
        - Delegates to verification_service for SHA-256 salted anonymized hashing.
        - Guarantees that raw identification digits are never stored in the database.
        - Inserts an audit entry into MySQL `simulated_verifications`.
        - Updates voter `simulated_verification_status` to 'SIMULATED_VERIFIED'.
        """
        from backend.app.services.verification_service import verification_service
        return verification_service.process_anonymized_verification(
            voter_id=voter_id,
            booth_id=booth_id,
            raw_identification=mock_input,
            verification_method=method,
            mock_input=mock_input
        )

# Singleton instance
auth_service = AuthService()
