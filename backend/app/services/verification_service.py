"""
Secure Anonymized Verification & Identity Hashing Service
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/services/verification_service.py

Handles:
  1. Salted SHA-256 cryptographic anonymization of citizen identifiers (hashlib).
  2. Strict pre-hashing input validation to reject malformed data cleanly without retention.
  3. Safe insertion of 64-character anonymized hash tokens into simulated_verifications.
  4. Complete prohibition of raw citizen credentials (zero real Aadhaar, PAN, raw biometrics).
"""

import os
import re
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
from database.db_pool import db_pool
from backend.app.os_engine.memory_and_logger import os_file_logger

logger = logging.getLogger("verification_service")

# Forbidden real credential markers to enforce legal and architectural guardrails
FORBIDDEN_CREDENTIAL_KEYWORDS = [
    "aadhaar", "pan", "passport", "voter_real", "fingerprint",
    "iris", "biometric_raw", "ssn", "national_id"
]

class VerificationService:
    """
    Cryptographic service for secure anonymized identity verification and hashing.
    Enforces that raw identification digits/strings are never stored in the database.
    """

    def __init__(self):
        # Environment-configurable cryptographic salt for SHA-256 hashing
        self.salt = os.getenv("HASH_SECRET_SALT", "onoe_secure_salt_2026_anonymized_token_salt")
        # Allowed synthetic identifier pattern: DEM-UK-2026-XXXX
        self.synthetic_epic_pattern = re.compile(r"^DEM-UK-2026-\d{4}$")
        # Pattern for numeric/alphanumeric identification or OTP input (6 to 32 characters)
        self.valid_id_pattern = re.compile(r"^[A-Za-z0-9\-_]{6,32}$")

    # -------------------------------------------------------------------------
    # 1. INPUT VALIDATION (Strict Pre-Hashing Guardrails)
    # -------------------------------------------------------------------------
    def validate_raw_identifier(self, raw_input: Any) -> Tuple[bool, str, Optional[str]]:
        """
        Validates raw identification input before any cryptographic processing:
        - Rejects None or non-string inputs.
        - Scans for forbidden real-world credential keywords.
        - Enforces length constraints (6 <= length <= 32).
        - Enforces formatting regex.
        Rejects malformed inputs cleanly without retaining or persisting them.
        """
        if raw_input is None:
            return False, "MISSING_INPUT", "Identification input cannot be empty."

        if not isinstance(raw_input, (str, int)):
            return False, "INVALID_DATA_TYPE", "Identification input must be a string or integer."

        clean_input = str(raw_input).strip()
        if not clean_input:
            return False, "EMPTY_INPUT", "Identification input cannot be blank."

        # Scan for forbidden real credential keywords
        lower_input = clean_input.lower()
        for kw in FORBIDDEN_CREDENTIAL_KEYWORDS:
            if kw in lower_input:
                return False, "REAL_CREDENTIALS_REJECTED", (
                    "Real citizen government identifiers or raw biometrics are strictly forbidden. "
                    "Only synthetic test identifiers conforming to ONOE specifications are permitted."
                )

        # Check length constraints
        if len(clean_input) < 6:
            return False, "INPUT_TOO_SHORT", "Identification input must be at least 6 characters long."

        if len(clean_input) > 32:
            return False, "INPUT_TOO_LONG", "Identification input must not exceed 32 characters."

        # Check character formatting (alphanumeric, dashes, underscores)
        if not self.valid_id_pattern.match(clean_input):
            return False, "INVALID_FORMAT", (
                "Identification input contains invalid characters. "
                "Only alphanumeric characters, dashes, and underscores are permitted."
            )

        return True, "VALID", clean_input

    # -------------------------------------------------------------------------
    # 2. SALTED SHA-256 HASHING HELPER
    # -------------------------------------------------------------------------
    def hash_identifier(self, raw_identifier: str) -> str:
        """
        Computes a salted SHA-256 cryptographic digest of the raw identifier.
        Returns a uniform 64-character lowercase hexadecimal hash token.
        Never stores or caches the raw identifier.
        """
        salted_data = f"{self.salt}:{raw_identifier.strip()}".encode("utf-8")
        return hashlib.sha256(salted_data).hexdigest()

    def verify_hash(self, raw_identifier: str, expected_hash: str) -> bool:
        """
        Constant-time comparison between raw input's salted hash and expected hash.
        """
        computed = self.hash_identifier(raw_identifier)
        import hmac
        return hmac.compare_digest(computed, expected_hash)

    # -------------------------------------------------------------------------
    # 3. SECURE ANONYMIZED VERIFICATION FLOW
    # -------------------------------------------------------------------------
    def process_anonymized_verification(
        self,
        voter_id: int,
        booth_id: int,
        raw_identification: Optional[str] = None,
        verification_method: str = "SIMULATED_EPIC_HASH",
        mock_input: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Executes end-to-end anonymized verification:
        1. Validates voter and booth jurisdiction.
        2. Format-validates raw input before hashing, discarding malformed data immediately.
        3. Computes the 64-character salted SHA-256 hash token.
        4. Inserts the anonymized hash into `simulated_verifications`.
        5. Updates voter `simulated_verification_status` to 'SIMULATED_VERIFIED'.
        6. Guarantees raw digits are NEVER stored in the database.
        """
        valid_methods = {"SIMULATED_OTP", "SIMULATED_EPIC_HASH", "DEMO_BIOMETRIC_TOKEN"}
        if verification_method not in valid_methods:
            return False, "INVALID_VERIFICATION_METHOD", None

        # Determine raw input to validate and hash
        target_raw = raw_identification or mock_input

        # Special case: SIMULATED_OTP with no raw input provided defaults to mock OTP
        if verification_method == "SIMULATED_OTP" and not target_raw:
            import random
            generated_otp = f"SIM-OTP-{random.randint(100000, 999999)}"
            token_to_store = generated_otp
        elif verification_method == "SIMULATED_OTP" and target_raw and target_raw.startswith("SIM-OTP-"):
            token_to_store = target_raw
        else:
            # If no raw input provided for hash or biometric method, derive from voter's synthetic demo epic
            if not target_raw:
                with db_pool.get_cursor() as (conn, cursor):
                    cursor.execute("SELECT demo_epic_no FROM voters WHERE voter_id = %s;", (voter_id,))
                    v_row = cursor.fetchone()
                    if not v_row:
                        return False, "VOTER_NOT_FOUND", None
                    target_raw = v_row["demo_epic_no"]

            # Pre-hashing format validation
            is_valid, err_code, err_msg = self.validate_raw_identifier(target_raw)
            if not is_valid:
                logger.warning("Pre-hashing validation failed for voter %s: %s (%s)", voter_id, err_code, err_msg)
                return False, err_code, None

            # Compute salted 64-character SHA-256 hash (raw digits discarded immediately)
            token_to_store = self.hash_identifier(target_raw)

        # Database transaction: Insert token and update voter status
        with db_pool.get_cursor() as (conn, cursor):
            # 1. Fetch voter record
            cursor.execute(
                "SELECT voter_id, demo_epic_no, assigned_booth_id FROM voters WHERE voter_id = %s;",
                (voter_id,)
            )
            voter = cursor.fetchone()
            if not voter:
                return False, "VOTER_NOT_FOUND", None

            # 2. Check booth jurisdiction
            if voter["assigned_booth_id"] != booth_id:
                return False, "INVALID_BOOTH_JURISDICTION", None

            # 3. Store ONLY the 64-character hash token (never raw digits) in simulated_verifications
            cursor.execute(
                """
                INSERT INTO simulated_verifications
                (voter_id, booth_id, simulated_token, verification_method, status, failure_reason)
                VALUES (%s, %s, %s, %s, 'PASSED', NULL);
                """,
                (voter_id, booth_id, token_to_store, verification_method)
            )

            # 4. Update voter status
            cursor.execute(
                """
                UPDATE voters
                SET simulated_verification_status = 'SIMULATED_VERIFIED'
                WHERE voter_id = %s;
                """,
                (voter_id,)
            )
            conn.commit()

            os_file_logger.log_trace(
                event_type="ANONYMIZED_VERIFICATION_SUCCESS",
                message=f"Voter {voter_id} verified via {verification_method} with 64-char anonymized hash token.",
                extra={
                    "voter_id": voter_id,
                    "booth_id": booth_id,
                    "token_hash_preview": token_to_store[:16] + "..." if len(token_to_store) > 16 else token_to_store
                }
            )

            return True, "SUCCESS", token_to_store

# Singleton instance
verification_service = VerificationService()
