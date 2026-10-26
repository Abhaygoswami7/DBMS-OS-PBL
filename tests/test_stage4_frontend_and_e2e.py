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
    """Verify that Flask correctly serves login.html, index.html, admin.html, styles.css, and JS scripts."""
    # 1. GET / & GET /login (IRCTC Authentication Gateway)
    res_login = client.get("/")
    assert res_login.status_code == 200
    assert "text/html" in res_login.content_type
    html_login = res_login.get_data(as_text=True)
    assert "VoteIT" in html_login
    assert "IRCTC Authentication Gateway" in html_login
    assert "VOTER LOGIN (DEFAULT)" in html_login
    assert "ADMIN CONTROL ROOM LOGIN" in html_login
    assert "btnProceedVoter" in html_login
    assert "btnAuthenticateAdmin" in html_login
    assert "stepper-container" in html_login
    assert "appointment-slip" in html_login

    res_login_route = client.get("/login")
    assert res_login_route.status_code == 200

    # 2. GET /voter & GET /index.html (Voter Booking Portal)
    res_voter = client.get("/voter")
    assert res_voter.status_code == 200
    assert "text/html" in res_voter.content_type
    html_voter = res_voter.get_data(as_text=True)
    assert "VoteIT" in html_voter
    assert "Smart Polling & Time-Slot Platform" in html_voter
    assert "Voter Arrival Scheduling & Digital Pass Portal" in html_voter
    assert "stepper-container" in html_voter
    assert "appointment-slip" in html_voter

    res_index_html = client.get("/index.html")
    assert res_index_html.status_code == 200

    # 3. GET /admin & GET /admin.html (Admin Dashboard)
    res_admin = client.get("/admin")
    assert res_admin.status_code == 200
    assert "text/html" in res_admin.content_type
    html_admin = res_admin.get_data(as_text=True)
    assert "VoteIT" in html_admin
    assert "Admin Logistics & Telemetry Console" in html_admin
    assert "Live OS Concurrency & Race Condition Simulator" in html_admin

    res_admin_html = client.get("/admin.html")
    assert res_admin_html.status_code == 200

    # 4. GET /css/styles.css (Core Stylesheet)
    res_css = client.get("/css/styles.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.content_type
    css_content = res_css.get_data(as_text=True)
    assert ":root" in css_content
    assert "high-contrast-mode" in css_content
    assert "pcb-pipeline" in css_content
    assert "appointment-slip" in css_content

    # 5. GET /js/api_client.js
    res_api_client = client.get("/js/api_client.js")
    assert res_api_client.status_code == 200
    js_api = res_api_client.get_data(as_text=True)
    assert "class ApiClient" in js_api
    assert "simulateRaceCondition" in js_api
    assert "checkVoterSession" in js_api
    assert "checkAdminAuth" in js_api

    # 6. GET /js/voter_portal.js
    res_vp = client.get("/js/voter_portal.js")
    assert res_vp.status_code == 200
    js_vp = res_vp.get_data(as_text=True)
    assert "goToStep" in js_vp
    assert "loadNearbyBooths" in js_vp

    # 7. GET /js/admin_dashboard.js
    res_ad = client.get("/js/admin_dashboard.js")
    assert res_ad.status_code == 200
    js_ad = res_ad.get_data(as_text=True)
    assert "btnRunRaceSimulation" in js_ad
    assert "loadCrowdPredictionsChart" in js_ad

    # 8. GET /assets/vote_logo.png (Branding Logo Asset)
    res_logo = client.get("/assets/vote_logo.png")
    assert res_logo.status_code == 200
    assert "image/png" in res_logo.content_type
    assert len(res_logo.data) > 1000


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
        res_booths = client.get("/api/booths/nearby?lat=29.3444&lon=79.5632&accessibility_needed=true")
        assert res_booths.status_code == 200
        data_booths = res_booths.get_json()
        assert data_booths["total_booths_found"] >= 1
        nearest_booth = data_booths["booths"][0]
        assert nearest_booth["distance_km"] > 0.0
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


# =============================================================================
# 4. DEADLOCK-SAFE RESCHEDULING & OS SCHEDULER POLICY TESTS
# =============================================================================

def test_deadlock_safe_slot_reschedule(client):
    """
    Verify PUT /api/allocations/<token>/reschedule:
      - Atomically moves booking from old_slot_id to new_slot_id.
      - Enforces Coffman circular-wait prevention: lock_acquisition_order sorted in ascending order.
      - Frees old slot capacity and reserves new slot capacity inside ACID transaction.
    """
    test_epic = "DEM-UK-2026-7788"

    # Clean up prior test runs
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute("DELETE FROM simulated_verifications WHERE voter_id IN (SELECT voter_id FROM voters WHERE demo_epic_no = %s);", (test_epic,))
        cursor.execute("DELETE FROM slot_allocations WHERE voter_id IN (SELECT voter_id FROM voters WHERE demo_epic_no = %s);", (test_epic,))
        cursor.execute("DELETE FROM voters WHERE demo_epic_no = %s;", (test_epic,))
        conn.commit()

    # Step A: Register synthetic voter
    res_reg = client.post("/api/voters/register", json={
        "demo_epic_no": test_epic,
        "full_name": "Deepak Joshi",
        "dob": "1991-03-21",
        "gender": "MALE",
        "assigned_booth_id": 1,
        "special_category": "GENERAL"
    })
    assert res_reg.status_code in (200, 201)
    voter_id = res_reg.get_json()["voter"]["voter_id"]

    try:
        # Step B: Initial Allocation in Slot 1
        res_alloc = client.post("/api/allocations", json={
            "voter_id": voter_id,
            "booth_id": 1,
            "slot_id": 1
        })
        assert res_alloc.status_code == 201
        initial_token = res_alloc.get_json()["booking_reference_token"]

        # Step C: Reschedule from Slot 1 to Slot 2
        res_resched = client.put(f"/api/allocations/{initial_token}/reschedule", json={
            "new_slot_id": 2
        })
        assert res_resched.status_code == 200
        data_resched = res_resched.get_json()

        assert data_resched["success"] is True
        assert data_resched["old_slot_id"] == 1
        assert data_resched["new_slot_id"] == 2
        assert data_resched["lock_acquisition_order"] == [1, 2]
        new_token = data_resched["booking_reference_token"]
        assert new_token.startswith("TKN-UK-")

        # Step D: Confirm appointment slip reflects new slot
        res_slip = client.get(f"/api/allocations/{new_token}")
        assert res_slip.status_code == 200
        slip = res_slip.get_json()["appointment_slip"]
        assert slip["slot_id"] == 2
        assert slip["booking_status"] == "CONFIRMED"

        # Step E: Clean up booking
        res_del = client.delete(f"/api/allocations/{new_token}")
        assert res_del.status_code == 200

    finally:
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("DELETE FROM simulated_verifications WHERE voter_id = %s;", (voter_id,))
            cursor.execute("DELETE FROM slot_allocations WHERE voter_id = %s;", (voter_id,))
            cursor.execute("DELETE FROM voters WHERE voter_id = %s;", (voter_id,))
            conn.commit()


def test_admin_scheduler_policy_comparator(client):
    """
    Verify POST /api/admin/scheduler-policy:
      - Toggles between FCFS and PRIORITY_AGING.
      - Dispatches 6-request simulation batch demonstrating starvation freedom via dynamic aging.
    """
    # 1. Test FCFS
    res_fcfs = client.post("/api/admin/scheduler-policy", json={"policy": "FCFS"})
    assert res_fcfs.status_code == 200
    data_fcfs = res_fcfs.get_json()
    assert data_fcfs["active_policy"] == "FCFS"
    order_fcfs = data_fcfs["simulation_batch"]["dispatched_order"]
    assert len(order_fcfs) == 6
    # In FCFS, dispatch rank matches arrival_index
    for item in order_fcfs:
        assert item["dispatch_rank"] == item["arrival_index"]

    # 2. Test PRIORITY_AGING
    res_aging = client.post("/api/admin/scheduler-policy", json={"policy": "PRIORITY_AGING"})
    assert res_aging.status_code == 200
    data_aging = res_aging.get_json()
    assert data_aging["active_policy"] == "PRIORITY_AGING"
    order_aging = data_aging["simulation_batch"]["dispatched_order"]
    assert len(order_aging) == 6

    # Verify that Priority Aging dispatches lower effective_priority values first
    eff_priorities = [item["effective_priority"] for item in order_aging]
    assert eff_priorities == sorted(eff_priorities)

    # 3. Test Invalid Policy Rejection
    res_invalid = client.post("/api/admin/scheduler-policy", json={"policy": "INVALID_POLICY"})
    assert res_invalid.status_code == 400


def test_admin_telemetry_export(client):
    """
    Verify GET /api/admin/telemetry-export:
      - Returns complete JSON telemetry snapshot including booths, ML metrics, and audit logs.
    """
    res = client.get("/api/admin/telemetry-export")
    assert res.status_code == 200
    data = res.get_json()
    assert "export_timestamp" in data
    assert "evaluation_metrics" in data
    assert "live_booth_status" in data
    assert "concurrency_audit_log" in data
    assert len(data["live_booth_status"]) > 0

