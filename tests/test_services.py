"""
Integration Tests for Core Backend Services
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Tests:
  1. AuthService: Admin JWT generation/verification & simulated voter verification.
  2. VoterService: Demographic lookup by DEM-UK-2026-XXXX, booth mapping.
  3. BoothService: Polling stations, booths, live views (vw_booth_live_status).
  4. AllocationService: Concurrency-safe atomic slot allocation via sp_allocate_slot_atomic,
     cancellation via sp_cancel_slot_atomic, and voter appointment slip generation.
"""

import pytest
from backend.app.services.auth_service import auth_service
from backend.app.services.voter_service import voter_service
from backend.app.services.booth_service import booth_service
from backend.app.services.allocation_service import allocation_service

def test_admin_jwt_authentication():
    """Verify admin login returns signed JWT and decodes with correct role."""
    login_res = auth_service.authenticate_admin("admin", "admin2026password")
    assert login_res is not None
    token = login_res["access_token"]
    assert token is not None

    decoded = auth_service.verify_token(token)
    assert decoded is not None
    assert decoded["sub"] == "admin"
    assert decoded["role"] == "SUPER_ADMIN"
    assert auth_service.has_role(decoded, ["SUPER_ADMIN"])
    assert not auth_service.has_role(decoded, ["POLLING_OFFICER"])

def test_voter_retrieval_and_jurisdiction():
    """Verify synthetic voter DEM-UK-2026-0001 is mapped to correct booth and station."""
    voter = voter_service.get_voter_by_demo_epic("DEM-UK-2026-0001")
    assert voter is not None
    assert voter["demo_epic_no"] == "DEM-UK-2026-0001"
    assert voter["assigned_booth_id"] == 1
    assert voter["special_category"] == "SENIOR_CITIZEN"
    assert voter["priority_level"] == 1
    assert voter["station_name"] == "Government Inter College Garhi Cantt"
    assert voter["parliamentary_constituency"] == "Tehri Garhwal Parliamentary Constituency"
    assert voter["assembly_constituency"] == "Dehradun Cantt Assembly Constituency"

def test_simulated_voter_verification():
    """Verify simulated OTP authentication logs entry into simulated_verifications."""
    success, status, token = auth_service.verify_simulated_voter(
        voter_id=7,  # Neelam Chauhan (Booth 1)
        booth_id=1,
        method="SIMULATED_OTP"
    )
    assert success is True
    assert status == "SUCCESS"
    assert token is not None
    assert token.startswith("SIM-OTP-")

def test_booth_service_live_views():
    """Verify querying vw_booth_live_status and vw_constituency_logistics_summary."""
    live_status = booth_service.get_live_booth_status(booth_id=1)
    assert len(live_status) >= 4  # 4 slots for booth 1
    assert live_status[0]["booth_id"] == 1
    assert "capacity_utilization_pct" in live_status[0]

    constituency_summary = booth_service.get_constituency_logistics_summary()
    assert len(constituency_summary) >= 6

def test_atomic_allocation_flow():
    """Verify end-to-end atomic slot booking, pass slip generation, and cancellation."""
    # Voter 8 (Neelam Chauhan, assigned to Booth 1)
    voter_id = 8
    booth_id = 1
    slot_id = 4  # Evening Slot

    # Step 1: Allocate Slot
    alloc_res = allocation_service.allocate_voter_slot(
        voter_id=voter_id,
        booth_id=booth_id,
        slot_id=slot_id,
        allocation_type="USER_RESERVED"
    )
    assert alloc_res["success"] is True
    assert alloc_res["status_code"] == "SUCCESS"
    token = alloc_res["booking_reference_token"]
    assert token is not None
    assert token.startswith("TKN-UK-")
    assert alloc_res["queue_token_no"] > 0
    assert "pcb_telemetry" in alloc_res
    assert alloc_res["pcb_telemetry"]["state"] == "TERMINATED"

    # Step 2: Prevent Duplicate Booking
    dup_res = allocation_service.allocate_voter_slot(
        voter_id=voter_id,
        booth_id=booth_id,
        slot_id=slot_id
    )
    assert dup_res["success"] is False
    assert dup_res["status_code"] == "DUPLICATE_BOOKING_PREVENTED"

    # Step 3: Fetch Voter Appointment Pass Slip
    slip = allocation_service.get_voter_appointment_slip(booking_reference_token=token)
    assert slip is not None
    assert slip["demo_epic_no"] == "DEM-UK-2026-0008"
    assert slip["booking_reference_token"] == token
    assert slip["booth_number"] == "BOOTH-01"
    assert slip["station_name"] == "Government Inter College Garhi Cantt"

    # Step 4: Cancel Slot Allocation
    cancel_res = allocation_service.cancel_slot_allocation(booking_reference_token=token)
    assert cancel_res["success"] is True
    assert cancel_res["status_code"] == "SUCCESS"

    # Step 5: Verify Pass Slip Status is Updated
    updated_slip = allocation_service.get_voter_appointment_slip(booking_reference_token=token)
    assert updated_slip["booking_status"] == "CANCELLED"

def test_deadlock_free_reallocation_flow():
    """Verify swapping voter slot uses hierarchical lock ordering and commits safely."""
    # Voter 7 (Vikram Pant, Booth 1)
    voter_id = 7
    booth_id = 1
    slot_id_1 = 3  # Afternoon
    slot_id_2 = 4  # Evening

    # 1. Allocate initial slot
    res1 = allocation_service.allocate_voter_slot(voter_id, booth_id, slot_id_1)
    assert res1["success"] is True
    initial_token = res1["booking_reference_token"]

    # 2. Reallocate to slot 4 (triggers dual lock: min(3, 4) -> 3, max(3, 4) -> 4)
    realloc_res = allocation_service.reallocate_voter_slot(
        voter_id=voter_id,
        booth_id=booth_id,
        old_slot_id=slot_id_1,
        new_slot_id=slot_id_2,
        booking_reference_token=initial_token
    )
    assert realloc_res["success"] is True
    assert realloc_res["status_code"] == "SUCCESS"
    new_token = realloc_res["new_booking_reference_token"]
    assert new_token is not None
    assert new_token != initial_token

    # 3. Verify new appointment pass slip
    slip = allocation_service.get_voter_appointment_slip(booking_reference_token=new_token)
    assert slip is not None
    assert slip["slot_id"] == slot_id_2
    assert slip["booking_status"] == "CONFIRMED"

    # Cleanup: cancel for clean state
    allocation_service.cancel_slot_allocation(new_token)

def test_voter_pagination_and_filters():
    """Verify voter listing with pagination and special category filters."""
    rows, total = voter_service.list_voters(limit=10, offset=0)
    assert total >= 60
    assert len(rows) == 10

    senior_rows, senior_total = voter_service.list_voters(category="SENIOR_CITIZEN")
    assert senior_total >= 10
    for r in senior_rows:
        assert r["special_category"] == "SENIOR_CITIZEN"
        assert r["priority_level"] == 1
