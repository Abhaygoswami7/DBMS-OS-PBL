"""
Stage 4 End-to-End & Frontend Integration Test Suite
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: tests/test_stage4_frontend_and_e2e.py

Validates:
  1. Flask Static File Serving:
     - GET / (Voter Portal HTML)
     - GET /admin and GET /admin.html (Admin Logistics & OS Telemetry Dashboard HTML)
     - GET /css/styles.css (Responsive Design System Stylesheet)
     - GET /js/api_client.js (API Client Wrapper)
     - GET /js/voter_portal.js (Voter Portal Controller)
     - GET /js/admin_dashboard.js (Admin Dashboard Controller)
  2. Complete End-to-End Voter Journey:
     - Synthetic Registration -> Simulated ECI Verification -> Geospatial Nearby Booths ->
       Available Slots with AI Crowd Prediction -> Atomic Slot Allocation (OS Mutex) ->
       Digital Appointment Slip Inspection -> Atomic Cancellation.
  3. Live Viva 10-Thread OS Mutex & Row-Lock Race Simulation (POST /api/admin/simulate-race):
     - Confirms exactly 1 thread succeeds (SUCCESS) and 9 threads are rejected (SLOT_CAPACITY_EXCEEDED).
     - Confirms zero overbooking under severe concurrent contention.
"""

import pytest
from database.db_pool import db_pool
from backend.app import create_app

@pytest.fixture(scope="module")
def app():
    """Module-level Flask application instance in testing mode."""
    test_app = create_app({"TESTING": True})
    return test_app

@pytest.fixture(scope="module")
def client(app):
    """Test client for issuing HTTP requests."""
    return app.test_client()


# =============================================================================
# 1. FRONTEND STATIC FILE SERVING TESTS
# =============================================================================

def test_frontend_static_serving(client):
    """Verify that Flask correctly serves index.html, admin.html, styles.css, and JS scripts."""
    # 1. GET / (Voter Portal)
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "text/html" in res_index.content_type
    html_index = res_index.get_data(as_text=True)
    assert "Smart Polling & Time-Slot Platform" in html_index
    assert "Voter Arrival Scheduling & Digital Pass Portal" in html_index
    assert "stepper-container" in html_index
    assert "appointment-slip" in html_index

    # 2. GET /admin & GET /admin.html (Admin Dashboard)
    res_admin = client.get("/admin")
    assert res_admin.status_code == 200
    assert "text/html" in res_admin.content_type
    html_admin = res_admin.get_data(as_text=True)
    assert "Admin Logistics & Telemetry Console" in html_admin
    assert "Live OS Concurrency & Race Condition Simulator" in html_admin

    res_admin_html = client.get("/admin.html")
    assert res_admin_html.status_code == 200

    # 3. GET /css/styles.css (Core Stylesheet)
    res_css = client.get("/css/styles.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.content_type
    css_content = res_css.get_data(as_text=True)
    assert ":root" in css_content
    assert "high-contrast-mode" in css_content
    assert "pcb-pipeline" in css_content
    assert "appointment-slip" in css_content

    # 4. GET /js/api_client.js
    res_api_client = client.get("/js/api_client.js")
    assert res_api_client.status_code == 200
    js_api = res_api_client.get_data(as_text=True)
    assert "class ApiClient" in js_api
    assert "simulateRaceCondition" in js_api

    # 5. GET /js/voter_portal.js
    res_vp = client.get("/js/voter_portal.js")
    assert res_vp.status_code == 200
    js_vp = res_vp.get_data(as_text=True)
    assert "goToStep" in js_vp
    assert "loadNearbyBooths" in js_vp

    # 6. GET /js/admin_dashboard.js
    res_ad = client.get("/js/admin_dashboard.js")
    assert res_ad.status_code == 200
    js_ad = res_ad.get_data(as_text=True)
    assert "btnRunRaceSimulation" in js_ad
    assert "loadCrowdPredictionsChart" in js_ad


# =============================================================================
# 2. COMPLETE END-TO-END VOTER JOURNEY TEST
# =============================================================================

def test_complete_end_to_end_voter_journey(client):
    """
    Executes the complete 7-step transactional voter lifecycle:
      1. Register new synthetic voter (DEM-UK-2026-9292, age >= 18).
      2. Simulated ECI identity verification with explicit consent.
      3. Geospatial discovery of nearby polling booths via Haversine distance.
      4. Querying available discretized slots enriched with Random Forest crowd predictions.
      5. Atomic slot allocation via sp_allocate_slot_atomic & per-slot mutex.
      6. Querying verified digital appointment pass slip (vw_voter_appointment_slip).
      7. Atomic cancellation via sp_cancel_slot_atomic and slot capacity restoration.
    """
    test_epic = "DEM-UK-2026-9292"

    # Clean up prior test runs
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute("DELETE FROM simulated_verifications WHERE voter_id IN (SELECT voter_id FROM voters WHERE demo_epic_no = %s);", (test_epic,))
        cursor.execute("DELETE FROM slot_allocations WHERE voter_id IN (SELECT voter_id FROM voters WHERE demo_epic_no = %s);", (test_epic,))
        cursor.execute("DELETE FROM voters WHERE demo_epic_no = %s;", (test_epic,))
        conn.commit()

    # Step 1: Register Synthetic Voter (201 Created)
    res_reg = client.post("/api/voters/register", json={
        "demo_epic_no": test_epic,
        "full_name": "Kavita Bhandari",
        "dob": "1994-08-12",
        "gender": "FEMALE",
        "assigned_booth_id": 1,
        "special_category": "PREGNANT_WOMEN"
    })
    assert res_reg.status_code in (200, 201)
    voter_data = res_reg.get_json()["voter"]
    voter_id = voter_data["voter_id"]
    assert voter_id > 0
    assert voter_data["demo_epic_no"] == test_epic

    try:
        # Step 2: Simulated ECI Verification with Explicit Consent (200 OK)
        res_verif = client.post("/api/verification/mock", json={
            "voter_id": voter_id,
            "booth_id": 1,
            "consent_given": True,
            "verification_method": "SIMULATED_OTP"
        })
        assert res_verif.status_code == 200
        data_verif = res_verif.get_json()
        assert data_verif["status"] == "PASSED"
        assert data_verif["simulated_token"].startswith("SIM-OTP-")

        # Step 3: Haversine Geo-Ranked Nearby Booths (200 OK)
        res_booths = client.get("/api/booths/nearby?lat=30.34215&lon=78.02148&accessibility_needed=true")
        assert res_booths.status_code == 200
        data_booths = res_booths.get_json()
        assert data_booths["total_booths_found"] >= 1
        nearest_booth = data_booths["booths"][0]
        assert nearest_booth["distance_km"] < 1.0
        assert nearest_booth["has_wheelchair_ramp"] is True

        # Step 4: Available Slots with AI Crowd Prediction (200 OK)
        res_slots = client.get(f"/api/slots/available?booth_id=1&voter_id={voter_id}")
        assert res_slots.status_code == 200
        data_slots = res_slots.get_json()
        assert data_slots["slots_count"] == 4
        # Verify AI recommendation is present
        assert "recommendation" in data_slots
        assert data_slots["recommendation"]["recommended_slot_id"] is not None
        target_slot_id = data_slots["slots"][2]["slot_id"]  # Afternoon slot

        # Step 5: Concurrency-Safe Atomic Slot Allocation (201 Created)
        res_alloc = client.post("/api/allocations", json={
            "voter_id": voter_id,
            "booth_id": 1,
            "slot_id": target_slot_id,
            "allocation_type": "USER_RESERVED"
        })
        assert res_alloc.status_code == 201
        data_alloc = res_alloc.get_json()
        assert data_alloc["status"] == "CONFIRMED"
        token = data_alloc["booking_reference_token"]
        assert token.startswith("TKN-UK-")
        assert data_alloc["queue_number"] > 0
        assert data_alloc["pcb_telemetry"]["state"] == "TERMINATED"

        # Step 6: Query Verified Digital Appointment Pass Slip (200 OK)
        res_slip = client.get(f"/api/allocations/{token}")
        assert res_slip.status_code == 200
        data_slip = res_slip.get_json()["appointment_slip"]
        assert data_slip["booking_reference_token"] == token
        assert data_slip["voter_id"] == voter_id
        assert data_slip["full_name"] == "Kavita Bhandari"
        assert data_slip["booking_status"] == "CONFIRMED"
        assert data_slip["slot_id"] == target_slot_id

        # Step 7: Atomic Cancellation & Capacity Restoration (200 OK)
        res_cancel = client.delete(f"/api/allocations/{token}")
        assert res_cancel.status_code == 200
        assert res_cancel.get_json()["status"] == "CANCELLED"

        # Verify slip status updated to CANCELLED
        res_updated_slip = client.get(f"/api/allocations/{token}")
        assert res_updated_slip.get_json()["appointment_slip"]["booking_status"] == "CANCELLED"

    finally:
        # Cleanup voter entity
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("DELETE FROM simulated_verifications WHERE voter_id = %s;", (voter_id,))
            cursor.execute("DELETE FROM slot_allocations WHERE voter_id = %s;", (voter_id,))
            cursor.execute("DELETE FROM voters WHERE voter_id = %s;", (voter_id,))
            conn.commit()


# =============================================================================
# 3. LIVE VIVA DEMO: 10-THREAD RACE SIMULATION TEST
# =============================================================================

def test_simulate_race_10_threads_zero_overbooking(client):
    """
    Verify POST /api/admin/simulate-race:
      - Simulates 10 concurrent OS threads via threading.Barrier competing for 1 seat.
      - Exactly 1 thread succeeds (SUCCESS) and 9 threads are rejected (SLOT_FULL_CAPACITY_EXCEEDED).
      - Zero overbooking is verified (zero_overbooking_verified == True).
    """
    res = client.post("/api/admin/simulate-race")
    assert res.status_code == 200
    data = res.get_json()

    assert data["success"] is True
    summary = data["summary"]
    assert summary["total_threads"] == 10
    assert summary["slot_max_capacity"] == 1
    assert summary["success_count"] == 1, f"Expected 1 winner, got {summary['success_count']}"
    assert summary["rejected_count"] == 9, f"Expected 9 rejected, got {summary['rejected_count']}"
    assert summary["zero_overbooking_verified"] is True

    # Winner verification
    winner = data["winner"]
    assert winner is not None
    assert winner["status"] == "SUCCESS"
    assert winner["booking_reference_token"].startswith("TKN-UK-")
    assert winner["queue_token_no"] == 1

    # Detailed per-thread verification
    thread_results = data["thread_results"]
    assert len(thread_results) == 10
    success_threads = [t for t in thread_results if t["status"] == "SUCCESS"]
    blocked_threads = [t for t in thread_results if t["status"] != "SUCCESS"]

    assert len(success_threads) == 1
    assert len(blocked_threads) == 9

    for bt in blocked_threads:
        assert bt["is_winner"] is False
        assert "SLOT_FULL_CAPACITY_EXCEEDED" in bt["status"] or "SLOT_CAPACITY_EXCEEDED" in bt["status"]
