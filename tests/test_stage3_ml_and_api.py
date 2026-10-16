"""
Integration & Regression Test Suite: Stage 3 (AI/ML Pipeline & All 12 REST API Endpoints)
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
File: tests/test_stage3_ml_and_api.py

Validates:
  1. AI/ML Crowd Prediction Pipeline & Artifacts:
     - Baseline vs. Random Forest Regressor evaluation metrics.
     - Confirms Random Forest achieves strictly lower MAE and RMSE than Baseline.
     - Automatic rule-based fallback when ML model is toggled offline.
     - Mandatory legal advisory guardrails present in predictions.
  2. All 12 REST API Endpoints across backend/:
     - POST /api/auth/login (Admin & Voter session authentication)
     - POST /api/voters/register (Voter registration, DOB age >= 18 check, synthetic EPIC validation)
     - POST /api/verification/mock (Simulated verification, consent check, rejection of real IDs)
     - GET /api/booths/nearby (Haversine ranking, wheelchair ramp filter)
     - GET /api/slots/available (Discretized slots enriched with AI crowd predictions & recommendations)
     - POST /api/allocations (OS PCB lifecycle, mutex critical section, sp_allocate_slot_atomic, 409 conflict)
     - GET /api/allocations/<id> (Digital appointment slip from vw_voter_appointment_slip)
     - DELETE /api/allocations/<id> (Atomic cancellation via sp_cancel_slot_atomic)
     - GET /api/admin/dashboard (RBAC, aggregated logistics views, alerts, OS telemetry)
     - POST /api/admin/booths (Admin booth creation & validation)
     - POST /api/admin/slots (Admin slot capacity configuration & validation)
     - GET /api/admin/crowd-predictions (Admin crowd forecasts & Baseline vs. RF benchmark metrics)
  3. System Health Check & Telemetry Headers:
     - GET /api/health & X-OS-Concurrency-Engine headers.
"""

import os
import json
import pytest
from database.db_pool import db_pool
from backend.app import create_app
from backend.app.services.crowd_prediction_service import crowd_prediction_service, LEGAL_GUARDRAIL_ADVISORY
from backend.app.services.auth_service import auth_service

@pytest.fixture(scope="module")
def app():
    """Module-level Flask application instance in testing mode."""
    test_app = create_app({"TESTING": True})
    return test_app

@pytest.fixture(scope="module")
def client(app):
    """Test client for issuing REST API requests."""
    return app.test_client()

@pytest.fixture(scope="module")
def admin_token():
    """Generates a valid Super Admin JWT token."""
    login_res = auth_service.authenticate_admin("admin", "admin2026password")
    assert login_res is not None
    return login_res["access_token"]

@pytest.fixture(scope="module")
def officer_token():
    """Generates a valid Polling Officer JWT token."""
    login_res = auth_service.authenticate_admin("officer_ddn", "officer2026password")
    assert login_res is not None
    return login_res["access_token"]

@pytest.fixture(scope="module")
def voter_token():
    """Generates a valid Voter Session JWT token."""
    login_res = auth_service.authenticate_voter_session(demo_epic_no="DEM-UK-2026-0001")
    assert login_res is not None
    return login_res["access_token"]


# =============================================================================
# 1. AI/ML PIPELINE & FALLBACK TESTS
# =============================================================================

def test_ml_artifacts_exist_and_rf_outperforms_baseline():
    """Verify ML training artifacts exist and Random Forest achieves lower MAE/RMSE than Baseline."""
    artifacts_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "ml_pipeline", "artifacts")
    )
    rf_model_path = os.path.join(artifacts_dir, "rf_crowd_model.joblib")
    scaler_path = os.path.join(artifacts_dir, "feature_scaler.joblib")
    metrics_path = os.path.join(artifacts_dir, "evaluation_metrics.json")
    dataset_path = os.path.join(artifacts_dir, "synthetic_crowd_history.csv")

    assert os.path.exists(rf_model_path), "rf_crowd_model.joblib not found"
    assert os.path.exists(scaler_path), "feature_scaler.joblib not found"
    assert os.path.exists(metrics_path), "evaluation_metrics.json not found"
    assert os.path.exists(dataset_path), "synthetic_crowd_history.csv not found"

    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    baseline_metrics = metrics["baseline_model"]["metrics"]
    rf_metrics = metrics["random_forest_model"]["metrics"]

    # Quantitative verification: Random Forest must outperform Baseline
    assert rf_metrics["mae"] < baseline_metrics["mae"], (
        f"RF MAE ({rf_metrics['mae']}) should be lower than Baseline MAE ({baseline_metrics['mae']})"
    )
    assert rf_metrics["rmse"] < baseline_metrics["rmse"], (
        f"RF RMSE ({rf_metrics['rmse']}) should be lower than Baseline RMSE ({baseline_metrics['rmse']})"
    )
    assert rf_metrics["r2_score"] > baseline_metrics["r2_score"], (
        f"RF R2 ({rf_metrics['r2_score']}) should be higher than Baseline R2 ({baseline_metrics['r2_score']})"
    )
    assert metrics["comparison"]["rf_outperforms_baseline"] is True

    # Feature importances must be present for all 10 features
    feature_importances = metrics["random_forest_model"]["feature_importances"]
    assert len(feature_importances) == 10
    assert "is_peak_morning_wave" in feature_importances
    assert "onoe_dual_ballot_factor" in feature_importances


def test_automatic_rule_based_fallback_and_guardrails(monkeypatch):
    """Verify seamless rule-based fallback when ML is toggled offline, and legal guardrail inclusion."""
    slot_data = {
        "slot_id": 1,
        "slot_date": "2026-11-15",
        "start_time": "09:30:00",
        "end_time": "12:00:00",
        "max_capacity": 40,
        "allocated_count": 8,
        "priority_reserved_capacity": 10
    }

    # 1. Test standard ML inference
    pred_ml = crowd_prediction_service.predict_slot_demand(booth_id=1, slot_row=slot_data)
    assert pred_ml["prediction_source"] == "RANDOM_FOREST_ML"
    assert pred_ml["predicted_arrivals"] >= 8
    assert pred_ml["congestion_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert pred_ml["legal_guardrail"]["is_advisory_only"] is True
    assert pred_ml["legal_guardrail"]["statement"] == LEGAL_GUARDRAIL_ADVISORY

    # 2. Test toggle offline via ML_FALLBACK_ENABLED
    monkeypatch.setenv("ML_FALLBACK_ENABLED", "true")
    assert crowd_prediction_service.is_ml_enabled() is False

    pred_fallback = crowd_prediction_service.predict_slot_demand(booth_id=1, slot_row=slot_data)
    assert pred_fallback["prediction_source"] == "RULE_BASED_FALLBACK"
    assert pred_fallback["predicted_arrivals"] >= 8
    assert pred_fallback["congestion_level"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert pred_fallback["legal_guardrail"]["is_advisory_only"] is True

    # Restore environment
    monkeypatch.setenv("ML_FALLBACK_ENABLED", "false")
    assert crowd_prediction_service.is_ml_enabled() is True


def test_smart_slot_recommendation_logic():
    """Verify recommend_optimal_slot balances Haversine distance, remaining capacity, and crowd load."""
    rec = crowd_prediction_service.recommend_optimal_slot(
        lat=30.34215,
        lon=78.02148,
        accessibility_needed=True
    )
    assert rec["recommendation_found"] is True
    assert "recommended_booth_id" in rec
    assert "recommended_slot_id" in rec
    assert rec["available_capacity"] > 0
    assert rec["distance_km"] >= 0.0
    assert len(rec["recommendation_reason"]) > 20
    assert rec["legal_guardrail"]["is_advisory_only"] is True


# =============================================================================
# 2. REST API ENDPOINTS TESTS (All 12 Endpoints)
# =============================================================================

# Endpoint 1: POST /api/auth/login
def test_endpoint_1_auth_login(client):
    """Test POST /api/auth/login for admin, voter sessions, and error handling."""
    # 1. Valid Admin Login
    res_admin = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin2026password"
    })
    assert res_admin.status_code == 200
    data_admin = res_admin.get_json()
    assert data_admin["success"] is True
    assert data_admin["access_token"] is not None
    assert data_admin["user"]["role"] == "SUPER_ADMIN"

    # 2. Valid Officer Login
    res_officer = client.post("/api/auth/login", json={
        "username": "officer_ddn",
        "password": "officer2026password"
    })
    assert res_officer.status_code == 200
    data_officer = res_officer.get_json()
    assert data_officer["user"]["role"] == "POLLING_OFFICER"

    # 3. Invalid Admin Password (401)
    res_bad = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "wrong_password"
    })
    assert res_bad.status_code == 401
    assert res_bad.get_json()["error"] == "UNAUTHORIZED"

    # 4. Valid Voter Session Login
    res_voter = client.post("/api/auth/login", json={
        "demo_epic_no": "DEM-UK-2026-0001"
    })
    assert res_voter.status_code == 200
    data_voter = res_voter.get_json()
    assert data_voter["user"]["role"] == "VOTER"
    assert data_voter["user"]["demo_epic_no"] == "DEM-UK-2026-0001"

    # 5. Missing Credentials (400)
    res_empty = client.post("/api/auth/login", json={})
    assert res_empty.status_code == 400
    assert res_empty.get_json()["error"] == "BAD_REQUEST"


# Endpoint 2: POST /api/voters/register
def test_endpoint_2_voters_register(client):
    """Test POST /api/voters/register for lookup, new registration, age validation, and EPIC format."""
    # 1. Look up existing synthetic voter (200 OK)
    res_lookup = client.post("/api/voters/register", json={
        "demo_epic_no": "DEM-UK-2026-0001",
        "action": "lookup"
    })
    assert res_lookup.status_code == 200
    data_lookup = res_lookup.get_json()
    assert data_lookup["success"] is True
    assert data_lookup["voter"]["demo_epic_no"] == "DEM-UK-2026-0001"

    # 2. Reject invalid EPIC format (400 Bad Request)
    res_bad_epic = client.post("/api/voters/register", json={
        "demo_epic_no": "REAL-EPIC-123456",
        "action": "lookup"
    })
    assert res_bad_epic.status_code == 400
    assert res_bad_epic.get_json()["error"] == "INVALID_EPIC_FORMAT"

    # 3. Reject underage voter (400 Bad Request)
    res_underage = client.post("/api/voters/register", json={
        "demo_epic_no": "DEM-UK-2026-9876",
        "full_name": "Minor Citizen",
        "dob": "2015-05-10",
        "gender": "FEMALE",
        "assigned_booth_id": 1
    })
    assert res_underage.status_code == 400
    assert res_underage.get_json()["error"] == "UNDERAGE_VOTER"

    # 4. Clean up test EPIC if exists, then register new voter (201 Created)
    test_epic = "DEM-UK-2026-9191"
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute("DELETE FROM voters WHERE demo_epic_no = %s;", (test_epic,))
        conn.commit()

    res_reg = client.post("/api/voters/register", json={
        "demo_epic_no": test_epic,
        "full_name": "Tara Singh Rawat",
        "dob": "1992-04-15",
        "gender": "MALE",
        "assigned_booth_id": 1,
        "special_category": "GENERAL"
    })
    assert res_reg.status_code == 201
    data_reg = res_reg.get_json()
    assert data_reg["success"] is True
    assert data_reg["status"] == "REGISTERED"
    assert data_reg["voter"]["demo_epic_no"] == test_epic


# Endpoint 3: POST /api/verification/mock
def test_endpoint_3_verification_mock(client):
    """Test POST /api/verification/mock with consent check and strict rejection of real IDs."""
    # 1. Valid simulated verification with explicit consent (200 OK)
    res_valid = client.post("/api/verification/mock", json={
        "voter_id": 12,
        "booth_id": 2,
        "consent_given": True,
        "verification_method": "SIMULATED_OTP"
    })
    assert res_valid.status_code == 200
    data_valid = res_valid.get_json()
    assert data_valid["success"] is True
    assert data_valid["status"] == "PASSED"
    assert data_valid["simulated_token"].startswith("SIM-OTP-")

    # 2. Reject verification when consent is missing/false (400 Bad Request)
    res_no_consent = client.post("/api/verification/mock", json={
        "voter_id": 12,
        "booth_id": 2,
        "consent_given": False
    })
    assert res_no_consent.status_code == 400
    assert res_no_consent.get_json()["error"] == "CONSENT_REQUIRED"

    # 3. Reject forbidden real government credentials (400 Bad Request)
    res_real_id = client.post("/api/verification/mock", json={
        "voter_id": 12,
        "booth_id": 2,
        "consent_given": True,
        "aadhaar_card_number": "1234-5678-9012"
    })
    assert res_real_id.status_code == 400
    assert res_real_id.get_json()["error"] == "REAL_CREDENTIALS_REJECTED"


# Endpoint 4: GET /api/booths/nearby
def test_endpoint_4_booths_nearby(client):
    """Test GET /api/booths/nearby with geospatial ranking and accessibility filtering."""
    # 1. Valid query with Dehradun GPS coordinates (200 OK)
    res = client.get("/api/booths/nearby?lat=30.34215&lon=78.02148")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["total_booths_found"] >= 8
    # Nearest booth should be booth 1 or 2 (Garhi Cantt)
    assert data["booths"][0]["distance_km"] < 0.1

    # 2. Filter by wheelchair accessibility
    res_access = client.get("/api/booths/nearby?lat=30.34215&lon=78.02148&accessibility_needed=true")
    assert res_access.status_code == 200
    for b in res_access.get_json()["booths"]:
        assert b["has_wheelchair_ramp"] is True

    # 3. Invalid coordinates (400 Bad Request)
    res_bad = client.get("/api/booths/nearby?lat=not_a_float&lon=not_a_float")
    assert res_bad.status_code == 400
    assert res_bad.get_json()["error"] == "BAD_REQUEST"


# Endpoint 5: GET /api/slots/available
def test_endpoint_5_slots_available(client):
    """Test GET /api/slots/available returns enriched slots with AI crowd demand and recommendations."""
    # 1. Valid query for Booth 1
    res = client.get("/api/slots/available?booth_id=1&event_id=1")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["slots_count"] == 4
    first_slot = data["slots"][0]
    assert "available_capacity" in first_slot
    assert "occupancy_status" in first_slot
    assert "ai_crowd_forecast" in first_slot
    assert "predicted_arrivals" in first_slot["ai_crowd_forecast"]
    assert "congestion_level" in first_slot["ai_crowd_forecast"]
    assert data["legal_guardrail"]["is_advisory_only"] is True

    # 2. Missing booth_id parameter (400 Bad Request)
    res_missing = client.get("/api/slots/available")
    assert res_missing.status_code == 400
    assert res_missing.get_json()["error"] == "BAD_REQUEST"

    # 3. Non-existent booth_id (404 Not Found)
    res_not_found = client.get("/api/slots/available?booth_id=9999")
    assert res_not_found.status_code == 404
    assert res_not_found.get_json()["error"] == "NOT_FOUND"


# Endpoint 6, 7, 8: POST /api/allocations, GET /api/allocations/<id>, DELETE /api/allocations/<id>
def test_endpoints_6_7_8_allocations_flow_and_conflict(client):
    """Test allocation creation, duplicate 409 conflict, slip retrieval, and atomic cancellation."""
    # Voter 14 (Meenakshi Thapliyal, assigned to Booth 2)
    voter_id = 14
    booth_id = 2
    slot_id = 8  # Evening Slot Booth 2

    # Cleanup any existing allocation for voter 14 first to guarantee clean slate
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute("UPDATE slot_allocations SET status = 'CANCELLED' WHERE voter_id = %s;", (voter_id,))
        conn.commit()

    # 1. Create Allocation (201 Created)
    res_create = client.post("/api/allocations", json={
        "voter_id": voter_id,
        "booth_id": booth_id,
        "slot_id": slot_id,
        "allocation_type": "USER_RESERVED"
    })
    assert res_create.status_code == 201
    data_create = res_create.get_json()
    assert data_create["success"] is True
    assert data_create["status"] == "CONFIRMED"
    token = data_create["booking_reference_token"]
    assert token.startswith("TKN-UK-")
    assert data_create["queue_number"] > 0
    assert "pcb_telemetry" in data_create
    assert data_create["pcb_telemetry"]["state"] == "TERMINATED"

    # 2. Duplicate Booking Conflict (409 Conflict)
    res_dup = client.post("/api/allocations", json={
        "voter_id": voter_id,
        "booth_id": booth_id,
        "slot_id": slot_id
    })
    assert res_dup.status_code == 409
    assert res_dup.get_json()["error"] == "CONFLICT"
    assert res_dup.get_json()["status_code"] == "DUPLICATE_BOOKING_PREVENTED"

    # 3. Missing Fields (400 Bad Request)
    res_missing = client.post("/api/allocations", json={"voter_id": voter_id})
    assert res_missing.status_code == 400
    assert res_missing.get_json()["error"] == "BAD_REQUEST"

    # 4. Retrieve Appointment Slip by Token (200 OK)
    res_slip = client.get(f"/api/allocations/{token}")
    assert res_slip.status_code == 200
    data_slip = res_slip.get_json()
    assert data_slip["success"] is True
    assert data_slip["appointment_slip"]["booking_reference_token"] == token
    assert data_slip["appointment_slip"]["voter_id"] == voter_id

    # 5. Retrieve Appointment Slip Non-existent (404 Not Found)
    res_slip_404 = client.get("/api/allocations/TKN-NON-EXISTENT-TOKEN")
    assert res_slip_404.status_code == 404
    assert res_slip_404.get_json()["error"] == "NOT_FOUND"

    # 6. Cancel Active Allocation Atomically (200 OK)
    res_cancel = client.delete(f"/api/allocations/{token}")
    assert res_cancel.status_code == 200
    data_cancel = res_cancel.get_json()
    assert data_cancel["success"] is True
    assert data_cancel["status"] == "CANCELLED"

    # 7. Cancel Already Cancelled Allocation (404 Not Found)
    res_cancel_again = client.delete(f"/api/allocations/{token}")
    assert res_cancel_again.status_code == 404
    assert res_cancel_again.get_json()["error"] == "NOT_FOUND"


# Endpoint 9: GET /api/admin/dashboard
def test_endpoint_9_admin_dashboard(client, admin_token, voter_token):
    """Test GET /api/admin/dashboard with RBAC protection (401, 403, 200)."""
    # 1. Missing Token (401 Unauthorized)
    res_no_auth = client.get("/api/admin/dashboard")
    assert res_no_auth.status_code == 401
    assert res_no_auth.get_json()["error"] == "UNAUTHORIZED"

    # 2. Voter Token Insufficient Privileges (403 Forbidden)
    res_voter_forbidden = client.get("/api/admin/dashboard", headers={
        "Authorization": f"Bearer {voter_token}"
    })
    assert res_voter_forbidden.status_code == 403
    assert res_voter_forbidden.get_json()["error"] == "FORBIDDEN"

    # 3. Super Admin Token (200 OK)
    res_admin = client.get("/api/admin/dashboard", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert res_admin.status_code == 200
    data = res_admin.get_json()
    assert data["success"] is True
    assert "live_booth_status" in data
    assert "constituency_logistics_summary" in data
    assert "overloaded_booth_alerts" in data
    assert "os_concurrency_telemetry" in data
    assert "lru_cache" in data["os_concurrency_telemetry"]


# Endpoint 10: POST /api/admin/booths
def test_endpoint_10_admin_booths(client, admin_token, officer_token):
    """Test POST /api/admin/booths with elevated admin RBAC and input validation."""
    # 1. Missing Token (401 Unauthorized)
    res_unauth = client.post("/api/admin/booths", json={})
    assert res_unauth.status_code == 401

    # 2. Polling Officer cannot create booths (403 Forbidden)
    res_officer = client.post("/api/admin/booths", json={}, headers={
        "Authorization": f"Bearer {officer_token}"
    })
    assert res_officer.status_code == 403

    # 3. Missing Fields with Admin Token (400 Bad Request)
    res_bad = client.post("/api/admin/booths", json={"station_id": 1}, headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert res_bad.status_code == 400
    assert res_bad.get_json()["error"] == "BAD_REQUEST"

    # 4. Valid Booth Creation (201 Created)
    res_create = client.post("/api/admin/booths", json={
        "station_id": 1,
        "pc_id": 2,
        "ac_id": 3,
        "booth_number": f"TEST-B-{int(os.getpid()) % 1000}",
        "booth_name": "Test Auxiliary Logistics Booth",
        "room_number": "Aux Room 99",
        "max_capacity_per_slot": 40,
        "evm_units_count": 2
    }, headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert res_create.status_code == 201
    assert res_create.get_json()["success"] is True
    new_booth_id = res_create.get_json()["booth_id"]

    # Clean up test booth
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute("DELETE FROM polling_booths WHERE booth_id = %s;", (new_booth_id,))
        conn.commit()


# Endpoint 11: POST /api/admin/slots
def test_endpoint_11_admin_slots(client, admin_token, voter_token):
    """Test POST /api/admin/slots for slot creation, update, and RBAC protection."""
    # 1. Unauthorized without token (401)
    res_no_auth = client.post("/api/admin/slots", json={})
    assert res_no_auth.status_code == 401

    # 2. Voter cannot configure slots (403)
    res_voter = client.post("/api/admin/slots", json={}, headers={
        "Authorization": f"Bearer {voter_token}"
    })
    assert res_voter.status_code == 403

    # 3. Missing fields (400 Bad Request)
    res_bad = client.post("/api/admin/slots", json={"booth_id": 1}, headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert res_bad.status_code == 400
    assert res_bad.get_json()["error"] == "BAD_REQUEST"

    # 4. Valid slot configuration update (200 OK)
    res_update = client.post("/api/admin/slots", json={
        "slot_id": 1,
        "booth_id": 1,
        "slot_date": "2026-11-15",
        "start_time": "07:00:00",
        "end_time": "09:30:00",
        "max_capacity": 40,
        "priority_reserved_capacity": 10
    }, headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert res_update.status_code == 200
    assert res_update.get_json()["success"] is True


# Endpoint 12: GET /api/admin/crowd-predictions
def test_endpoint_12_admin_crowd_predictions(client, admin_token, voter_token):
    """Test GET /api/admin/crowd-predictions returns forecasts and Baseline vs. RF metrics."""
    # 1. Unauthorized without token (401)
    res_no_auth = client.get("/api/admin/crowd-predictions")
    assert res_no_auth.status_code == 401

    # 2. Voter role forbidden (403)
    res_voter = client.get("/api/admin/crowd-predictions", headers={
        "Authorization": f"Bearer {voter_token}"
    })
    assert res_voter.status_code == 403

    # 3. Admin token returns full evaluation report & slot forecasts (200 OK)
    res_admin = client.get("/api/admin/crowd-predictions", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert res_admin.status_code == 200
    data = res_admin.get_json()
    assert data["success"] is True
    assert "evaluation_metrics" in data
    assert "baseline_model" in data["evaluation_metrics"]
    assert "random_forest_model" in data["evaluation_metrics"]
    assert data["evaluation_metrics"]["comparison"]["rf_outperforms_baseline"] is True
    assert len(data["slot_crowd_forecasts"]) >= 32  # 32 seeded slots across 8 booths
    assert data["legal_guardrail"]["is_advisory_only"] is True


# Health Check & OS Telemetry Headers
def test_health_check_and_os_telemetry_headers(client):
    """Test GET /api/health and verify OS telemetry headers are attached to responses."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert data["endpoints_ready"] == 12

    # Check custom OS engine headers
    assert res.headers.get("X-Platform") == "ONOE-Smart-Poll-2026"
    assert res.headers.get("X-OS-Concurrency-Engine") == "Active"
    assert "X-Response-Timestamp" in res.headers
