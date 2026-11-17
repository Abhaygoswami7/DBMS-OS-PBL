"""
Live Database & API End-to-End Test Suite
Tests all endpoints directly against the real MySQL 8.4 database (smart_poll_allocation_db).
"""

import json
import pytest
from backend.app import create_app
from database.db_pool import db_pool

@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def test_01_live_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert data["endpoints_ready"] == 12

def test_02_authoritative_voters_list(client):
    res = client.get("/api/voters?limit=15")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    voters = data["voters"]
    assert len(voters) > 0

    # Voter 1 (Ramesh Chandra Sharma) must have confirmed booking
    v1 = next((v for v in voters if v["voter_id"] == 1), None)
    assert v1 is not None
    assert v1["has_active_booking"] is True
    assert v1["active_token"] is not None
    assert abs(v1["latitude"] - 29.3751) < 0.001
    assert abs(v1["longitude"] - 79.5313) < 0.001

    # Voter 7 (Vikram Pant) must NOT have active confirmed booking
    v7 = next((v for v in voters if v["voter_id"] == 7), None)
    assert v7 is not None
    assert v7["has_active_booking"] is False
    assert v7["active_token"] is None

def test_03_voter_lookup_with_active_booking(client):
    res = client.post("/api/voters/register", json={
        "demo_epic_no": "DEM-UK-2026-0001",
        "action": "lookup"
    })
    assert res.status_code == 200
    data = res.get_json()
    voter = data["voter"]
    assert voter["voter_id"] == 1
    assert voter["full_name"] == "Ramesh Chandra Sharma"
    assert voter["has_active_booking"] is True
    assert voter["active_booking"] is not None
    assert voter["active_booking"]["booking_reference_token"] == "TKN-UK-1-1763180400-1001"
    assert voter["active_booking"]["status"] == "CONFIRMED"

def test_04_voter_lookup_without_active_booking(client):
    res = client.post("/api/voters/register", json={
        "demo_epic_no": "DEM-UK-2026-0007",
        "action": "lookup"
    })
    assert res.status_code == 200
    data = res.get_json()
    voter = data["voter"]
    assert voter["voter_id"] == 7
    assert voter["full_name"] == "Vikram Pant"
    assert voter["has_active_booking"] is False
    assert voter["active_booking"] is None

def test_05_nearby_booths_geospatial_accuracy(client):
    res = client.get("/api/booths/nearby?lat=29.3751&lon=79.5313&voter_id=1")
    assert res.status_code == 200
    data = res.get_json()
    booths = data["booths"]
    assert len(booths) > 0

    # Assigned Booth 1 must be Rank 1 with 0.00 km distance
    assert booths[0]["booth_id"] == 1
    assert booths[0]["distance_km"] == 0.0
    assert booths[0]["is_registered_booth"] is True

    # No 148 km Bhimtal anomaly: All booths must be under 50 km
    for b in booths:
        assert b["distance_km"] < 50.0

def test_06_jurisdiction_guard_on_slots(client):
    # Voter 1 is registered at Booth 1. Requesting Booth 2 slots must be rejected with 403
    res_ineligible = client.get("/api/slots/available?booth_id=2&voter_id=1")
    assert res_ineligible.status_code == 403
    data = res_ineligible.get_json()
    assert data["error"] == "INVALID_BOOTH_JURISDICTION"

    # Requesting Booth 1 slots for Voter 1 must succeed
    res_eligible = client.get("/api/slots/available?booth_id=1&voter_id=1")
    assert res_eligible.status_code == 200
    data_el = res_eligible.get_json()
    assert len(data_el["slots"]) > 0
    assert data_el["booth"]["booth_id"] == 1
    assert data_el["recommendation"]["recommended_slot_id"] is not None

def test_07_prevent_duplicate_booking_for_active_voter(client):
    # Voter 1 already has confirmed booking TKN-UK-1-1763180400-1001
    res = client.post("/api/allocations", json={
        "voter_id": 1,
        "booth_id": 1,
        "slot_id": 2,
        "allocation_type": "USER_RESERVED"
    })
    assert res.status_code == 409
    data = res.get_json()
    assert data["status_code"] == "DUPLICATE_BOOKING_PREVENTED"
    assert "already possesses an active confirmed booking" in data["message"]

def test_08_new_booking_and_cancellation_lifecycle(client):
    # Voter 7 (Vikram Pant) has NO active booking. Book Slot 4 (booth 1).
    book_payload = {
        "voter_id": 7,
        "booth_id": 1,
        "slot_id": 4,
        "allocation_type": "USER_RESERVED"
    }
    book_res = client.post("/api/allocations", json=book_payload)

    # If lingering from prior test run, cancel first
    if book_res.status_code == 409:
        v_res = client.post("/api/voters/register", json={"demo_epic_no": "DEM-UK-2026-0007", "action": "lookup"})
        existing_token = v_res.get_json()["voter"]["active_booking"]["booking_reference_token"]
        client.delete(f"/api/allocations/{existing_token}")
        book_res = client.post("/api/allocations", json=book_payload)

    assert book_res.status_code == 201
    book_data = book_res.get_json()
    assert book_data["success"] is True
    assert book_data["status"] == "CONFIRMED"
    token = book_data["booking_reference_token"]
    assert token.startswith("TKN-UK-4-")

    # Verify appointment slip is retrievable via vw_voter_appointment_slip
    slip_res = client.get(f"/api/allocations/{token}")
    assert slip_res.status_code == 200
    slip = slip_res.get_json()["appointment_slip"]
    assert slip["full_name"] == "Vikram Pant"
    assert slip["booking_status"] == "CONFIRMED"
    assert slip["slot_id"] == 4

    # Atomically cancel slot allocation via sp_cancel_slot_atomic
    del_res = client.delete(f"/api/allocations/{token}")
    assert del_res.status_code == 200
    del_data = del_res.get_json()
    assert del_data["status"] == "CANCELLED"

    # Verify voter 7 no longer has an active confirmed booking
    v7_res = client.post("/api/voters/register", json={"demo_epic_no": "DEM-UK-2026-0007", "action": "lookup"})
    assert v7_res.get_json()["voter"]["has_active_booking"] is False

def test_09_deadlock_safe_rescheduling(client):
    # Lookup voter 2's current active booking dynamically
    v_res = client.post("/api/voters/register", json={"demo_epic_no": "DEM-UK-2026-0002", "action": "lookup"})
    v_data = v_res.get_json()
    assert v_data["voter"]["has_active_booking"] is True
    current_token = v_data["voter"]["active_booking"]["booking_reference_token"]
    current_slot = v_data["voter"]["active_booking"]["slot_id"]
    target_slot = 3 if current_slot != 3 else 1

    # Reschedule from current_slot to target_slot (both in Booth 1)
    res = client.put(f"/api/allocations/{current_token}/reschedule", json={"new_slot_id": target_slot})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["lock_acquisition_order"] == [min(current_slot, target_slot), max(current_slot, target_slot)]
    new_token = data["new_booking_reference_token"]

    # Reschedule back to restore original slot
    res_back = client.put(f"/api/allocations/{new_token}/reschedule", json={"new_slot_id": current_slot})
    assert res_back.status_code == 200
    data_back = res_back.get_json()
    assert data_back["success"] is True
    assert data_back["lock_acquisition_order"] == [min(current_slot, target_slot), max(current_slot, target_slot)]
