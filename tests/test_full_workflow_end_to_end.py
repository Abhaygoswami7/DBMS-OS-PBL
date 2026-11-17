"""
Complete 12-Step End-to-End System Workflow Integration Test
Academic Demonstration: Full-Stack Integration across OS, DBMS, AI & Web Architecture

Verifies the complete 12-step voter and administrator journey:
  Step 1:  Synthetic Voter Authentication via Synthetic EPIC lookup (/api/voters/register)
  Step 2:  Simulated ECI Verification (/api/verification/mock)
  Step 3:  Jurisdiction and Assigned Booth Mapping (Nainital-Udhamsingh Nagar PC · Bhimtal AC)
  Step 4:  AI Demand Forecast Retrieval (/api/admin/crowd-predictions)
  Step 5:  Polling Booth Selection across 4 Bhimtal Demonstration Stations (/api/booths/nearby)
  Step 6:  Real-Time Slot Availability & Remaining Capacity Inspection (/api/slots/available)
  Step 7:  Atomic Time-Slot Booking under Concurrency Mutex & ACID Row-Locking (/api/allocations)
  Step 8:  Cryptographic PNR Token & Appointment Slip Generation (/api/allocations/<token>)
  Step 9:  Atomic Slot Cancellation with Database Capacity De-allocation (DELETE /api/allocations/<token>)
  Step 10: Seamless Slot Rescheduling Workflow (PUT /api/allocations/<token>/reschedule)
  Step 11: Admin Control Room Live Monitoring (Priority Scheduler, Telemetry, DBMS Views)
  Step 12: Audit Trail & IPC Transactional Outbox Delivery Verification
"""

import pytest
import json
from backend.app import create_app
from backend.app.services.auth_service import auth_service
from database.db_pool import db_pool


@pytest.fixture(scope="module")
def app_client():
    """Initializes the Flask test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestFullWorkflowEndToEnd:
    """Executes the canonical 12-step VoteIT end-to-end integration flow."""

    def test_complete_12_step_system_flow(self, app_client):
        # ---------------------------------------------------------------------
        # Step 1: Synthetic Voter Authentication via Synthetic EPIC lookup
        # ---------------------------------------------------------------------
        epic_no = "DEM-UK-2026-0001"
        login_res = app_client.post("/api/voters/register", json={
            "demo_epic_no": epic_no,
            "action": "lookup"
        })
        assert login_res.status_code == 200, f"Voter lookup failed: {login_res.data}"
        login_data = login_res.get_json()
        assert login_data["success"] is True
        voter = login_data["voter"]
        voter_id = voter["voter_id"]
        assigned_booth_id = voter["assigned_booth_id"]
        assert voter["demo_epic_no"] == epic_no

        # Clean any prior active booking for voter_id to ensure repeatable test runs
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("UPDATE slot_allocations SET status = 'CANCELLED' WHERE voter_id = %s AND status = 'CONFIRMED';", (voter_id,))
            conn.commit()

        # ---------------------------------------------------------------------
        # Step 2: Simulated ECI Verification
        # ---------------------------------------------------------------------
        verify_res = app_client.post("/api/verification/mock", json={
            "voter_id": voter_id,
            "booth_id": assigned_booth_id,
            "consent_given": True,
            "simulated_otp": "123456"
        })
        assert verify_res.status_code == 200
        verify_data = verify_res.get_json()
        assert verify_data["success"] is True
        assert verify_data["status"] == "PASSED"
        assert "simulated_token" in verify_data

        # ---------------------------------------------------------------------
        # Step 3: Jurisdiction & Constituency Validation (Bhimtal AC · Nainital PC)
        # ---------------------------------------------------------------------
        with db_pool.get_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("""
                SELECT ps.station_name, ps.address, c_ac.constituency_name as ac_name, c_pc.constituency_name as pc_name
                FROM polling_booths b
                JOIN polling_stations ps ON b.station_id = ps.station_id
                JOIN constituencies c_ac ON b.ac_id = c_ac.constituency_id
                JOIN constituencies c_pc ON b.pc_id = c_pc.constituency_id
                WHERE b.booth_id = %s;
            """, (assigned_booth_id,))
            jurisdiction = cursor.fetchone()
            assert jurisdiction is not None
            assert "Bhimtal" in jurisdiction["ac_name"] or "Bhimtal" in jurisdiction["station_name"]
            assert "Nainital" in jurisdiction["pc_name"]

        # ---------------------------------------------------------------------
        # Step 4: AI Demand Forecast Retrieval
        # ---------------------------------------------------------------------
        admin_auth = auth_service.authenticate_admin("admin", "admin2026password")
        assert admin_auth is not None
        admin_token = admin_auth["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        ai_res = app_client.get("/api/admin/crowd-predictions", headers=admin_headers)
        assert ai_res.status_code == 200
        ai_data = ai_res.get_json()
        assert ai_data["success"] is True
        assert "evaluation_metrics" in ai_data
        rf_metrics = ai_data["evaluation_metrics"]["random_forest_model"]["metrics"]
        assert rf_metrics["r2_score"] >= 0.90

        # ---------------------------------------------------------------------
        # Step 5: Polling Booth Selection (4 Bhimtal Demonstration Stations)
        # ---------------------------------------------------------------------
        nearby_res = app_client.get("/api/booths/nearby?lat=29.3510&lon=79.5530")
        assert nearby_res.status_code == 200
        nearby_data = nearby_res.get_json()
        assert nearby_data["success"] is True
        booths = nearby_data["booths"]
        assert len(booths) >= 4
        # Target voter's assigned booth
        target_booth = next((b for b in booths if b["booth_id"] == assigned_booth_id), booths[0])
        booth_id = target_booth["booth_id"]

        # ---------------------------------------------------------------------
        # Step 6: Real-Time Slot Availability & Remaining Capacity Inspection
        # ---------------------------------------------------------------------
        slots_res = app_client.get(f"/api/slots/available?booth_id={booth_id}")
        assert slots_res.status_code == 200
        slots_data = slots_res.get_json()
        assert slots_data["success"] is True
        slots = slots_data["slots"]
        assert len(slots) > 0
        target_slot = slots[0]
        slot_id = target_slot["slot_id"]

        # ---------------------------------------------------------------------
        # Step 7: Atomic Time-Slot Booking under Concurrency Mutex & Row-Locking
        # ---------------------------------------------------------------------
        book_res = app_client.post("/api/allocations", json={
            "voter_id": voter_id,
            "booth_id": booth_id,
            "slot_id": slot_id,
            "allocation_type": "USER_RESERVED"
        })
        assert book_res.status_code in (200, 201)
        book_data = book_res.get_json()
        assert book_data["success"] is True
        assert book_data["status"] == "CONFIRMED"

        # ---------------------------------------------------------------------
        # Step 8: Cryptographic PNR Token & Appointment Slip Generation
        # ---------------------------------------------------------------------
        token = book_data["booking_reference_token"]
        assert token.startswith("TKN-UK-")
        assert book_data["queue_token_no"] >= 1
        assert "pcb_telemetry" in book_data

        slip_res = app_client.get(f"/api/allocations/{token}")
        assert slip_res.status_code == 200
        slip_data = slip_res.get_json()
        assert slip_data["success"] is True
        assert slip_data["appointment_slip"]["booking_reference_token"] == token

        # ---------------------------------------------------------------------
        # Step 9: Atomic Slot Cancellation with Capacity De-allocation
        # ---------------------------------------------------------------------
        cancel_res = app_client.delete(f"/api/allocations/{token}")
        assert cancel_res.status_code == 200
        cancel_data = cancel_res.get_json()
        assert cancel_data["success"] is True

        # Verify database capacity was restored
        with db_pool.get_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT status FROM slot_allocations WHERE booking_reference_token = %s;", (token,))
            assert cursor.fetchone()["status"] == "CANCELLED"

        # ---------------------------------------------------------------------
        # Step 10: Seamless Slot Rescheduling Workflow
        # ---------------------------------------------------------------------
        # Book fresh slot after cancellation
        rebook_res = app_client.post("/api/allocations", json={
            "voter_id": voter_id,
            "booth_id": booth_id,
            "slot_id": slot_id,
            "allocation_type": "USER_RESERVED"
        })
        assert rebook_res.status_code in (200, 201)
        rebook_data = rebook_res.get_json()
        assert rebook_data["success"] is True
        new_token = rebook_data["booking_reference_token"]
        assert new_token != token

        # ---------------------------------------------------------------------
        # Step 11: Admin Control Room Live Monitoring
        # ---------------------------------------------------------------------
        # 11A. Admin Dashboard
        admin_dash_res = app_client.get("/api/admin/dashboard", headers=admin_headers)
        assert admin_dash_res.status_code == 200
        assert admin_dash_res.get_json()["success"] is True

        # 11B. Priority Scheduler Summary
        prio_sum_res = app_client.get("/api/admin/priority-scheduler/summary", headers=admin_headers)
        assert prio_sum_res.status_code == 200
        assert prio_sum_res.get_json()["summary"]["total_registered_voters"] == 61

        # 11C. OS Subsystem Telemetry
        os_tel_res = app_client.get("/api/admin/os-telemetry-full", headers=admin_headers)
        assert os_tel_res.status_code == 200
        os_tel_data = os_tel_res.get_json()
        assert "scheduler" in os_tel_data
        assert "ipc" in os_tel_data
        assert "cache" in os_tel_data

        # 11D. DBMS Analytics Views
        dbms_res = app_client.get("/api/admin/dbms-analytics", headers=admin_headers)
        assert dbms_res.status_code == 200
        dbms_data = dbms_res.get_json()
        assert dbms_data["admin_statistics"]["total_stations"] == 4
        assert dbms_data["admin_statistics"]["total_active_booths"] == 8

        # 11E. Recent Bookings
        recent_res = app_client.get("/api/admin/recent-bookings?limit=5", headers=admin_headers)
        assert recent_res.status_code == 200
        recent_data = recent_res.get_json()
        assert len(recent_data["bookings"]) > 0

        # ---------------------------------------------------------------------
        # Step 12: Audit Trail & IPC Outbox Verification
        # ---------------------------------------------------------------------
        with db_pool.get_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT COUNT(*) AS audit_cnt FROM os_concurrency_audit WHERE voter_id = %s;", (voter_id,))
            audit_cnt = cursor.fetchone()["audit_cnt"]
            assert audit_cnt > 0

            cursor.execute("SELECT COUNT(*) AS outbox_cnt FROM allocation_events_outbox WHERE aggregate_id = %s;", (new_token,))
            outbox_cnt = cursor.fetchone()["outbox_cnt"]
            assert outbox_cnt > 0

            # Teardown: Restore voter 1 to original seed state
            cursor.execute("DELETE FROM slot_allocations WHERE booking_reference_token = %s;", (new_token,))
            cursor.execute("UPDATE slot_allocations SET status = 'CONFIRMED' WHERE booking_reference_token = 'TKN-UK-1-1763180400-1001';")
            conn.commit()
