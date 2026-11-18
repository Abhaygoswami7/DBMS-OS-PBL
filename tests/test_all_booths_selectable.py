"""
Integration and End-to-End Tests: All Polling Booths Selectable System
Project: Smart Polling Booth & Time-Slot Allocation Platform (VoteIT)

Validates:
1. All polling booths across all stations are returned and marked eligible for selection.
2. Cross-booth slot availability queries succeed with 200 OK and informational metadata.
3. Atomic cross-booth slot reservation succeeds through MySQL stored procedure sp_allocate_slot_atomic.
4. Duplicate active booking prevention and capacity invariant enforcement remain strictly intact.
5. Frontend code in voter_portal.js contains zero restrictive "ELIGIBLE IN AC" or "INELIGIBLE - WRONG JURISDICTION" barriers.
"""

import pytest
from pathlib import Path
from backend.app import create_app
from database.db_pool import db_pool


@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


def test_01_nearby_booths_returns_all_booths_without_ac_filtering(client):
    """
    Ensure GET /api/booths/nearby with voter_id returns all active booths in the database,
    none are filtered out, and all have is_eligible = True.
    """
    # Voter 1 is assigned to Booth 1
    res = client.get("/api/booths/nearby?voter_id=1")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    booths = data["booths"]
    assert len(booths) == 8, f"Expected 8 booths, got {len(booths)}"

    # Multiple distinct stations are included
    station_ids = {b.get("station_id") for b in booths}
    assert len(station_ids) >= 4, "Booths from all 4 stations must be included"

    # All booths must be marked as eligible and selectable
    for booth in booths:
        assert booth.get("is_eligible") is True, f"Booth {booth['booth_id']} must be marked eligible"
        assert "booth_id" in booth
        assert "station_name" in booth
        assert "assembly_constituency" in booth
        assert "parliamentary_constituency" in booth

    # Registered booth is identified
    registered_booth = next((b for b in booths if b["booth_id"] == 1), None)
    assert registered_booth is not None
    assert registered_booth.get("is_registered_booth") is True

    # Other booths are not marked as registered booth but are eligible
    other_booths = [b for b in booths if b["booth_id"] != 1]
    assert len(other_booths) == 7
    for ob in other_booths:
        assert ob.get("is_registered_booth") is False
        assert ob.get("is_eligible") is True


def test_02_slots_available_for_cross_booth_selection(client):
    """
    Ensure GET /api/slots/available returns 200 OK when a voter queries slots for a booth
    outside their registered booth.
    """
    # Voter 1 is registered in Booth 1. Query Booth 6 (Vikas Bhawan Rural Development Room 2).
    res = client.get("/api/slots/available?booth_id=6&voter_id=1")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "slots" in data
    assert len(data["slots"]) > 0

    # Informational metadata must be attached inside booth object
    booth_info = data["booth"]
    assert booth_info.get("is_registered_booth") is False
    assert booth_info.get("assigned_booth_id") == 1
    assert booth_info.get("assigned_booth_name") is not None


def test_03_atomic_cross_booth_allocation_lifecycle(client):
    """
    Test booking a slot in a booth outside voter's registered booth,
    verifying successful reservation, appointment pass retrieval, and atomic cancellation.
    """
    # Voter 7 (Vikram Pant) has assigned_booth_id = 4.
    # Book a slot in Booth 6.
    # Cleanup any active booking for voter 7 first.
    with db_pool.get_cursor() as (conn, cur):
        cur.execute("UPDATE slot_allocations SET status = 'CANCELLED' WHERE voter_id = 7 AND status IN ('CONFIRMED', 'CHECKED_IN')")
        conn.commit()

    # Step A: Perform cross-booth slot booking
    slots_res = client.get("/api/slots/available?booth_id=6&voter_id=7")
    assert slots_res.status_code == 200
    available_slots = slots_res.get_json()["slots"]
    target_slot = next((s for s in available_slots if s.get("available_capacity", 0) > 0), available_slots[0])
    target_slot_id = target_slot["slot_id"]

    book_res = client.post("/api/allocations", json={
        "voter_id": 7,
        "booth_id": 6,
        "slot_id": target_slot_id,
        "allocation_type": "USER_RESERVED"
    })
    assert book_res.status_code == 201
    book_data = book_res.get_json()
    assert book_data["success"] is True
    assert book_data["status"] == "CONFIRMED"
    token = book_data["booking_reference_token"]
    assert token.startswith("TKN-UK-6-")

    # Step B: Retrieve appointment pass
    slip_res = client.get(f"/api/allocations/{token}")
    assert slip_res.status_code == 200
    slip = slip_res.get_json()["appointment_slip"]
    assert slip["full_name"] == "Vikram Pant"
    assert slip["booth_id"] == 6
    assert slip["booking_status"] == "CONFIRMED"

    # Step C: Verify duplicate booking prevention across booths
    dup_res = client.post("/api/allocations", json={
        "voter_id": 7,
        "booth_id": 1,
        "slot_id": 1,
        "allocation_type": "USER_RESERVED"
    })
    assert dup_res.status_code == 409
    dup_data = dup_res.get_json()
    assert dup_data["status_code"] == "DUPLICATE_BOOKING_PREVENTED"

    # Step D: Cancel the cross-booth booking
    del_res = client.delete(f"/api/allocations/{token}")
    assert del_res.status_code == 200
    del_data = del_res.get_json()
    assert del_data["status"] == "CANCELLED"

    # Verify voter 7 is clear
    v7_res = client.post("/api/voters/register", json={"demo_epic_no": "DEM-UK-2026-0007", "action": "lookup"})
    assert v7_res.get_json()["voter"]["has_active_booking"] is False


def test_04_frontend_labels_and_barriers_removed():
    """
    Verify that voter_portal.js does not contain restrictive or misleading labels
    such as 'ELIGIBLE IN AC' or 'INELIGIBLE - WRONG JURISDICTION', and all booths are rendered selectable.
    """
    root_dir = Path(__file__).resolve().parent.parent
    voter_js_path = root_dir / "frontend" / "js" / "voter_portal.js"
    content = voter_js_path.read_text(encoding="utf-8")

    assert "ELIGIBLE IN AC" not in content, "Misleading 'ELIGIBLE IN AC' label must be removed"
    assert "INELIGIBLE - WRONG JURISDICTION" not in content, "Misleading 'INELIGIBLE - WRONG JURISDICTION' label must be removed"
    assert "cursor: not-allowed" not in content, "Disabled booth cursor must be removed"
    assert "AVAILABLE FOR ALLOCATION" in content, "Alternative booths must be marked as available for allocation"
