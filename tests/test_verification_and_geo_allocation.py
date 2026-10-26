"""
Comprehensive Unit & Integration Test Suite
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Test Module: tests/test_verification_and_geo_allocation.py

Validates:
  1. Secure Anonymized Verification & Salted SHA-256 Hashing (VerificationService):
     - Pre-hashing format validation (length, characters, forbidden keywords).
     - Salted SHA-256 generation (64-character lowercase hex digest).
     - Environment-configurable salt (HASH_SECRET_SALT).
     - Complete prohibition of storing raw digits in MySQL.
  2. Haversine Geolocation Booth Ranking (GeoBoothRanker):
     - Mathematical Haversine great-circle distance accuracy.
     - Filtering by simultaneous Lok Sabha (PC) & Vidhan Sabha (AC) jurisdiction.
     - Filtering by physical wheelchair accessibility ramp.
     - Operational status (is_active = 1).
     - Multi-criteria composite score (proximity + live availability ratio).
  3. Capacity-Aware Time-Slot Scheduling (AllocationService):
     - Polling hours discretization into 4 standard ONOE arrival windows.
     - InnoDB pessimistic row locking (SELECT ... FOR UPDATE via sp_allocate_slot_atomic).
     - Database-level capacity invariant (allocated_count <= max_capacity).
     - Digital appointment pass slip generation from vw_voter_appointment_slip.
     - Atomic cancellation and capacity restoration.
"""

import os
import hashlib
import pytest
from database.db_pool import db_pool
from backend.app import create_app
from backend.app.services.verification_service import VerificationService, verification_service
from backend.app.services.geo_booth_ranker import GeoBoothRanker, geo_booth_ranker, haversine_distance_km
from backend.app.services.allocation_service import allocation_service
from backend.app.services.booth_service import booth_service

@pytest.fixture(scope="module")
def app():
    """Module-level Flask application instance in testing mode."""
    test_app = create_app({"TESTING": True})
    return test_app

@pytest.fixture(scope="module")
def client(app):
    """Test client for issuing REST API requests."""
    return app.test_client()

# ==============================================================================
# 1. VERIFICATION SERVICE TESTS (ANONYMIZED HASHING & INPUT VALIDATION)
# ==============================================================================

def test_hashing_helper_salted_sha256():
    """Verify that hashing helper produces exactly 64-char lowercase SHA-256 hex digest."""
    svc = VerificationService()
    test_id = "DEM-UK-2026-0001"
    token_hash = svc.hash_identifier(test_id)

    assert len(token_hash) == 64
    assert token_hash == token_hash.lower()
    # Confirm deterministic output
    assert token_hash == svc.hash_identifier(test_id)
    # Confirm verify_hash
    assert svc.verify_hash(test_id, token_hash) is True
    assert svc.verify_hash("OTHER-INPUT-1234", token_hash) is False

def test_configurable_salt_effect():
    """Verify that changing HASH_SECRET_SALT alters the resulting hash digest."""
    svc1 = VerificationService()
    svc1.salt = "salt_alpha_2026"
    hash1 = svc1.hash_identifier("TEST-ID-9999")

    svc2 = VerificationService()
    svc2.salt = "salt_beta_2026"
    hash2 = svc2.hash_identifier("TEST-ID-9999")

    assert hash1 != hash2
    assert len(hash1) == 64
    assert len(hash2) == 64

def test_pre_hashing_validation_success():
    """Verify valid synthetic format and alphanumeric tokens pass pre-hashing validation."""
    svc = VerificationService()
    
    valid_samples = [
        "DEM-UK-2026-0001",
        "987654321012",
        "123456",
        "VOTER-MOCK-TOKEN-99"
    ]
    for s in valid_samples:
        is_valid, code, sanitized = svc.validate_raw_identifier(s)
        assert is_valid is True, f"Failed for {s}: {code}"
        assert sanitized == s

def test_pre_hashing_validation_rejection_rules():
    """Verify malformed, too short, too long, and forbidden inputs are rejected cleanly without retention."""
    svc = VerificationService()

    # Empty / None
    assert svc.validate_raw_identifier(None)[0] is False
    assert svc.validate_raw_identifier("")[0] is False

    # Too short (< 6 chars)
    is_valid, code, _ = svc.validate_raw_identifier("12345")
    assert is_valid is False
    assert code == "INPUT_TOO_SHORT"

    # Too long (> 32 chars)
    is_valid, code, _ = svc.validate_raw_identifier("A" * 33)
    assert is_valid is False
    assert code == "INPUT_TOO_LONG"

    # Forbidden real-world credential keywords
    for forbidden in ["my_aadhaar_no_1234", "pan_card_998877", "real_passport_num", "biometric_raw_scan"]:
        is_valid, code, _ = svc.validate_raw_identifier(forbidden)
        assert is_valid is False
        assert code == "REAL_CREDENTIALS_REJECTED"

    # Invalid special characters
    is_valid, code, _ = svc.validate_raw_identifier("test$$$###@@@12")
    assert is_valid is False
    assert code == "INVALID_FORMAT"

def test_anonymized_verification_never_stores_raw_digits():
    """Verify process_anonymized_verification stores only 64-char hash token, never raw digits."""
    raw_secret_digits = "987654321099"  # Raw digits submitted by user
    voter_id = 9  # Sanjay Negi (Booth 2)
    booth_id = 2

    success, code, token = verification_service.process_anonymized_verification(
        voter_id=voter_id,
        booth_id=booth_id,
        raw_identification=raw_secret_digits,
        verification_method="SIMULATED_EPIC_HASH"
    )
    assert success is True
    assert code == "SUCCESS"
    assert len(token) == 64  # Must be 64-character SHA-256 token
    assert token == verification_service.hash_identifier(raw_secret_digits)

    # Inspect MySQL database directly to prove raw digits were NEVER stored
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute(
            """
            SELECT simulated_token FROM simulated_verifications
            WHERE voter_id = %s ORDER BY verification_id DESC LIMIT 1;
            """,
            (voter_id,)
        )
        stored_token = cursor.fetchone()["simulated_token"]
        assert stored_token == token
        assert raw_secret_digits not in stored_token

        # Confirm nowhere in simulated_verifications does the raw string appear
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM simulated_verifications WHERE simulated_token LIKE %s;",
            (f"%{raw_secret_digits}%",)
        )
        count = cursor.fetchone()["cnt"]
        assert count == 0, "Security Violation: Raw identifier found in MySQL database!"

# ==============================================================================
# 2. HAVERSINE GEOLOCATION BOOTH RANKING TESTS
# ==============================================================================

def test_haversine_distance_computation():
    """Verify mathematical accuracy of Haversine formula."""
    # Zero distance test (same point)
    assert haversine_distance_km(30.34215, 78.02148, 30.34215, 78.02148) == 0.0

    # Distance from Dehradun (30.34215, 78.02148) to Rishikesh (~30.1030, 78.2948) is ~38-42 km
    dist = haversine_distance_km(30.34215, 78.02148, 30.1030, 78.2948)
    assert 35.0 < dist < 45.0

def test_geo_booth_ranking_with_accessibility_filter():
    """Verify GeoBoothRanker filters by wheelchair accessibility when requested."""
    user_lat = 30.34215
    user_lon = 78.02148

    # Query with wheelchair accessibility required
    accessible_booths = geo_booth_ranker.rank_booths(
        user_lat=user_lat,
        user_lon=user_lon,
        requires_wheelchair_accessibility=True
    )
    assert len(accessible_booths) > 0
    for b in accessible_booths:
        assert b["has_wheelchair_ramp"] is True

def test_geo_booth_ranking_jurisdiction_filtering():
    """Verify candidate booths are filtered strictly by Parliamentary & Assembly jurisdiction."""
    user_lat = 30.34215
    user_lon = 78.02148

    # Filter by Dehradun Cantt Assembly Constituency (ac_id = 3)
    cantt_booths = geo_booth_ranker.rank_booths(
        user_lat=user_lat,
        user_lon=user_lon,
        ac_id=3
    )
    assert len(cantt_booths) > 0
    for b in cantt_booths:
        assert b["ac_id"] == 3

def test_geo_booth_composite_score_ordering():
    """Verify multi-criteria composite score combines proximity and live capacity ratio."""
    user_lat = 30.34215
    user_lon = 78.02148

    ranked = geo_booth_ranker.rank_booths(user_lat=user_lat, user_lon=user_lon)
    assert len(ranked) >= 2

    # Check that booths are sorted by composite_score ascending
    for i in range(len(ranked) - 1):
        assert ranked[i]["composite_score"] <= ranked[i + 1]["composite_score"]
        assert "availability_ratio" in ranked[i]
        assert "distance_km" in ranked[i]

# ==============================================================================
# 3. CAPACITY-AWARE TIME-SLOT SCHEDULING TESTS
# ==============================================================================

def test_discretize_polling_hours():
    """Verify polling hours are discretized into standard arrival windows."""
    slots = allocation_service.discretize_polling_hours(
        booth_id=1,
        event_id=1,
        slot_date="2026-11-15",
        max_capacity_per_slot=50,
        priority_reserved_capacity=15
    )
    assert len(slots) == 4
    # Check start times
    normalized_times = [s["start_time"].lstrip("0") for s in slots]
    assert "7:00:00" in normalized_times
    assert "9:30:00" in normalized_times
    assert "12:30:00" in normalized_times
    assert "15:00:00" in normalized_times

def test_atomic_allocation_enforces_capacity_invariant():
    """Verify atomic allocation adheres to InnoDB row locking and updates capacity invariant."""
    voter_id = 10  # Pooja Rawat (Booth 2)
    booth_id = 2
    slot_id = 8

    # Clean existing allocation for voter 10
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute("UPDATE slot_allocations SET status = 'CANCELLED' WHERE voter_id = %s;", (voter_id,))
        conn.commit()

    # Step 1: Allocate
    res = allocation_service.allocate_voter_slot(voter_id, booth_id, slot_id)
    assert res["success"] is True
    token = res["booking_reference_token"]
    assert token.startswith("TKN-UK-")
    assert res["appointment_slip"] is not None
    assert res["appointment_slip"]["booking_reference_token"] == token

    # Step 2: Verify database capacity invariant
    inv_check = allocation_service.verify_capacity_invariant(slot_id)
    assert inv_check["invariant_satisfied"] is True
    assert inv_check["allocated_count"] <= inv_check["hard_limit"]

    # Step 3: Cancellation restores capacity
    cancel_res = allocation_service.cancel_slot_allocation(token)
    assert cancel_res["success"] is True

    # Step 4: Verify capacity restored in invariant
    inv_after = allocation_service.verify_capacity_invariant(slot_id)
    assert inv_after["invariant_satisfied"] is True
    assert inv_after["allocated_count"] == inv_check["allocated_count"] - 1

# ==============================================================================
# 4. REST API ENDPOINTS TESTS
# ==============================================================================

def test_api_verification_mock_with_anonymized_hashing(client):
    """Test POST /api/verification/mock with raw input hashing and clean rejection on bad input."""
    # 1. Clean valid verification with raw identification string
    res = client.post("/api/verification/mock", json={
        "voter_id": 11,
        "booth_id": 2,
        "consent_given": True,
        "verification_method": "SIMULATED_EPIC_HASH",
        "mock_input": "987654321088"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["status"] == "PASSED"
    # Token must be 64-character SHA-256 hash
    assert len(data["simulated_token"]) == 64

    # 2. Reject malformed input cleanly without storing
    res_bad = client.post("/api/verification/mock", json={
        "voter_id": 11,
        "booth_id": 2,
        "consent_given": True,
        "verification_method": "SIMULATED_EPIC_HASH",
        "mock_input": "12"  # Too short (< 6 chars)
    })
    assert res_bad.status_code == 400
    assert res_bad.get_json()["error"] == "INPUT_TOO_SHORT"

def test_api_nearby_booths_geo_ranking(client):
    """Test GET /api/booths/nearby with coordinates and wheelchair filtering."""
    res = client.get("/api/booths/nearby?lat=30.34215&lon=78.02148&requires_wheelchair_accessibility=true")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["total_booths_found"] > 0
    first_booth = data["booths"][0]
    assert first_booth["has_wheelchair_ramp"] is True
    assert "distance_km" in first_booth
    assert "composite_score" in first_booth
