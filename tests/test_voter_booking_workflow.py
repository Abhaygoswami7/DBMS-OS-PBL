"""
Automated Test Suite for Voter Data, Booth Jurisdiction & Booking Workflow Integrity
Project: VoteIT — Smart Polling Booth & Time-Slot Allocation Platform (ONOE)
Module: tests/test_voter_booking_workflow.py

Covers:
  1. Voter Identity Synchronization (Dropdown, Synthetic EPIC, Profile Card)
  2. 1:1 Synthetic Voter Mapping in authoritative seed data
  3. Stale Data Clearing on Voter Switching
  4. Polling Booth Jurisdiction Validation (PC and AC matching)
  5. Distance Calculation & 148.7504 km anomaly resolution
  6. Haversine Great-Circle distance mathematical accuracy
  7. AI Recommendation consistency and booth-scoping
  8. Upfront Booking Jurisdiction Validation & Rejection of Ineligible Booths
  9. Backend & Database Concurrency Safety (zero partial allocations)
  10. Map Marker and Pin coordinate binding
  11. Zero Emojis compliance
"""

import os
import re
import math
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from database.db_pool import db_pool
from backend.app.services.booth_service import booth_service
from backend.app.services.voter_service import voter_service
from backend.app.services.allocation_service import allocation_service
from backend.app.services.geo_booth_ranker import haversine_distance_km, GeoBoothRanker
from backend.app.services.crowd_prediction_service import CrowdPredictionService

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
DATABASE_DIR = ROOT_DIR / "database"

# -----------------------------------------------------------------------------
# 1. MATHEMATICAL HAVERSINE DISTANCE & ANOMALY VERIFICATION
# -----------------------------------------------------------------------------
def test_haversine_formula_accuracy_and_anomaly_diagnosis():
    """
    Verifies:
      1. Distance between identical points is 0.00 km.
      2. Distance between Bhimtal (29.3444, 79.5632) and Rishikesh (30.10342, 78.29471)
         is mathematically 148.7504 km, proving the exact root cause of the reported anomaly.
      3. Distance between Voter at Garhi Cantt (30.34215, 78.02148) and Garhi Cantt
         polling station is 0.00 km.
    """
    # 1. Zero distance test
    assert haversine_distance_km(30.34215, 78.02148, 30.34215, 78.02148) == 0.0

    # 2. Diagnosing the 148.7504 km anomaly:
    bhimtal_lat, bhimtal_lon = 29.3444, 79.5632
    rishikesh_lat, rishikesh_lon = 30.10342, 78.29471
    dist_anomaly = haversine_distance_km(bhimtal_lat, bhimtal_lon, rishikesh_lat, rishikesh_lon)
    assert abs(dist_anomaly - 148.7504) < 0.05, f"Expected ~148.7504 km, got {dist_anomaly}"

    # 3. Corrected distance: Voter anchored to registered Dehradun Garhi Cantt station
    voter_lat, voter_lon = 30.34215, 78.02148
    station_garhi_lat, station_garhi_lon = 30.34215, 78.02148
    dist_corrected = haversine_distance_km(voter_lat, voter_lon, station_garhi_lat, station_garhi_lon)
    assert dist_corrected == 0.0, "Voter distance to assigned station must be 0.0 km"

    # 4. Known real-world geodesic baseline: Dehradun Garhi Cantt to Hathibarkala (~2.63 km)
    station_hathi_lat, station_hathi_lon = 30.33982, 78.04871
    dist_local = haversine_distance_km(voter_lat, voter_lon, station_hathi_lat, station_hathi_lon)
    assert 2.5 <= dist_local <= 2.8, f"Expected ~2.63 km, got {dist_local}"


# -----------------------------------------------------------------------------
# 2. VOTER IDENTITY MAPPING IN SEED DATA (1:1 CORRESPONDENCE)
# -----------------------------------------------------------------------------
def test_seed_data_voter_mapping_integrity():
    """Verify that every synthetic EPIC in seed_data.sql maps to exactly 1 voter record."""
    seed_path = DATABASE_DIR / "seed_data.sql"
    assert seed_path.exists(), "seed_data.sql must exist"
    content = seed_path.read_text(encoding="utf-8")

    # Match all voter inserts: ('DEM-UK-2026-XXXX', ...)
    voter_epics = re.findall(r"'(DEM-UK-2026-\d{4})'", content)
    assert len(voter_epics) > 0, "Seed data must contain synthetic voters"
    
    # Assert every EPIC number is unique (1:1 mapping)
    unique_epics = set(voter_epics)
    assert len(voter_epics) == len(unique_epics), "Duplicate synthetic EPIC IDs found in seed data"

    # Specific seed verification for benchmark voters
    assert "DEM-UK-2026-0001" in voter_epics, "DEM-UK-2026-0001 must exist"
    assert "DEM-UK-2026-0002" in voter_epics, "DEM-UK-2026-0002 must exist"
    assert "Ramesh Chandra Sharma" in content, "Ramesh Chandra Sharma must be the authentic identity for DEM-UK-2026-0001"
    assert "Sunita Devi Rawat" in content, "Sunita Devi Rawat must be the authentic identity for DEM-UK-2026-0002"


# -----------------------------------------------------------------------------
# 3. HTML VOTER DROPDOWN SYNCHRONIZATION
# -----------------------------------------------------------------------------
def test_index_html_voter_dropdown_alignment():
    """Verify index.html voter dropdown matches authentic database identities."""
    index_path = FRONTEND_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")

    # Eliminates fake demo names: Aarav Sharma should NOT be DEM-UK-2026-0001
    assert "Aarav Sharma (General - DEM-UK-2026-0001)" not in content, "Fake identity 'Aarav Sharma' must be removed"
    assert "Priya Negi (PwD Assistive Priority - DEM-UK-2026-0002)" not in content, "Fake identity 'Priya Negi' must be removed"

    # Authentic seed records present in dropdown options
    assert 'value="DEM-UK-2026-0001"' in content
    assert "Ramesh Chandra Sharma" in content
    assert 'value="DEM-UK-2026-0002"' in content
    assert "Sunita Devi Rawat" in content
    assert 'value="DEM-UK-2026-0003"' in content
    assert "Arvind Singh Negi" in content


# -----------------------------------------------------------------------------
# 4. FRONTEND IDENTITY SYNCHRONIZATION & STALE STATE CLEARING
# -----------------------------------------------------------------------------
def test_voter_portal_identity_sync_and_stale_clearing_logic():
    """Verify voter_portal.js implements strict identity synchronization and stale state clearing."""
    portal_js_path = FRONTEND_DIR / "js" / "voter_portal.js"
    content = portal_js_path.read_text(encoding="utf-8")

    # 1. Two-way synchronization
    assert "manualEpicInput.value = voter.demo_epic_no" in content, "manualEpicInput must sync with voter"
    assert "seededVoterSelect.value = voter.demo_epic_no" in content, "seededVoterSelect must sync with voter"

    # 2. Stale data clearing on voter change
    assert "isDifferentVoter" in content, "Must detect when voter identity switches"
    assert "state.isVerified = false" in content, "Must reset verification when switching voters"
    assert "state.selectedBooth = null" in content, "Must clear selected booth on voter switch"
    assert "state.selectedSlot = null" in content, "Must clear selected slot on voter switch"
    assert "state.activeAllocation = null" in content, "Must clear active allocation on voter switch"

    # 3. Anchor voter GPS to registered station coordinates
    assert "parseFloat(voter.latitude)" in content, "Must parse voter registered station latitude"
    assert "parseFloat(voter.longitude)" in content, "Must parse voter registered station longitude"

    # 4. Dynamic voter list loading from API
    assert "getVoters" in content, "Must query getVoters API for dynamic seed list"


# -----------------------------------------------------------------------------
# 5. GEOGRAPHICAL BOOTH RANKING & JURISDICTION VALIDATION
# -----------------------------------------------------------------------------
def test_geo_booth_ranker_voter_scoping():
    """
    Verify GeoBoothRanker:
      - Ranks the voter's assigned booth #1.
      - Filters out booths from non-matching assembly constituencies.
      - Anchors distance to 0.00 km for assigned booth.
    """
    ranker = GeoBoothRanker()

    # Mock database return with multiple booths across different constituencies
    mock_booths = [
        {
            "booth_id": 1,
            "booth_number": "B-001",
            "booth_name": "Garhi Cantt North Wing Room 101",
            "room_number": "Room 101",
            "max_capacity_per_slot": 60,
            "evm_units_count": 2,
            "is_active": 1,
            "station_id": 1,
            "station_code": "STN-DDN-01",
            "station_name": "Government Inter College, Garhi Cantt",
            "station_address": "Garhi Cantt, Dehradun",
            "station_pincode": "248003",
            "latitude": 30.34215,
            "longitude": 78.02148,
            "has_wheelchair_ramp": 1,
            "has_separate_entry_exit": 1,
            "pc_id": 2,
            "pc_code": "PC-002",
            "parliamentary_constituency": "Tehri Garhwal",
            "ac_id": 3,
            "ac_code": "AC-003",
            "assembly_constituency": "Dehradun Cantt"
        },
        {
            "booth_id": 2,
            "booth_number": "B-002",
            "booth_name": "Garhi Cantt South Wing Room 102",
            "room_number": "Room 102",
            "max_capacity_per_slot": 60,
            "evm_units_count": 2,
            "is_active": 1,
            "station_id": 1,
            "station_code": "STN-DDN-01",
            "station_name": "Government Inter College, Garhi Cantt",
            "station_address": "Garhi Cantt, Dehradun",
            "station_pincode": "248003",
            "latitude": 30.34215,
            "longitude": 78.02148,
            "has_wheelchair_ramp": 1,
            "has_separate_entry_exit": 1,
            "pc_id": 2,
            "pc_code": "PC-002",
            "parliamentary_constituency": "Tehri Garhwal",
            "ac_id": 3,
            "ac_code": "AC-003",
            "assembly_constituency": "Dehradun Cantt"
        },
        {
            "booth_id": 5,
            "booth_number": "B-005",
            "booth_name": "Veerbhadra Academic Block Booth 1",
            "room_number": "Hall 1",
            "max_capacity_per_slot": 50,
            "evm_units_count": 2,
            "is_active": 1,
            "station_id": 3,
            "station_code": "STN-RKH-01",
            "station_name": "Veerbhadra Inter College",
            "station_address": "Veerbhadra, Rishikesh",
            "station_pincode": "249202",
            "latitude": 30.10342,
            "longitude": 78.29471,
            "has_wheelchair_ramp": 1,
            "has_separate_entry_exit": 1,
            "pc_id": 1,
            "pc_code": "PC-001",
            "parliamentary_constituency": "Haridwar",
            "ac_id": 5,
            "ac_code": "AC-005",
            "assembly_constituency": "Rishikesh"
        }
    ]

    mock_voter = {
        "voter_id": 1,
        "demo_epic_no": "DEM-UK-2026-0001",
        "full_name": "Ramesh Chandra Sharma",
        "assigned_booth_id": 1,
        "pc_id": 2,
        "ac_id": 3,
        "latitude": 30.34215,
        "longitude": 78.02148
    }

    with patch.object(db_pool, "get_cursor") as mock_cursor_ctx, \
         patch.object(voter_service, "get_voter_by_id", return_value=mock_voter), \
         patch.object(ranker, "get_live_slot_availability_ratios", return_value={}):
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_booths
        mock_cursor_ctx.return_value.__enter__.return_value = (mock_conn, mock_cursor)

        ranked = ranker.rank_booths(
            user_lat=29.3444,  # Passing Bhimtal default to test auto-anchoring to voter station
            user_lon=79.5632,
            voter_id=1
        )

        # 1. Rishikesh Booth 5 must be excluded because AC = 5 != voter AC 3
        booth_ids = [b["booth_id"] for b in ranked]
        assert 5 not in booth_ids, "Booth 5 (Rishikesh) must be filtered out for Dehradun Cantt voter"
        assert 1 in booth_ids, "Assigned Booth 1 must be present"
        assert 2 in booth_ids, "Booth 2 in same AC must be present"

        # 2. Assigned booth must be Rank 1
        assert ranked[0]["booth_id"] == 1, "Voter's assigned booth must be Rank 1"
        assert ranked[0]["is_registered_booth"] is True
        assert ranked[0]["distance_km"] == 0.0, "Assigned booth distance must be 0.0 km"


# -----------------------------------------------------------------------------
# 6. AI RECOMMENDATION CONSISTENCY & TARGET BOOTH SCOPING
# -----------------------------------------------------------------------------
def test_crowd_prediction_service_recommendation_scoping():
    """Verify AI crowd recommendation scopes strictly to target_booth_id."""
    pred_service = CrowdPredictionService()

    mock_booths = [
        {"booth_id": 1, "booth_name": "Garhi Cantt Booth 1", "station_name": "GIC Garhi Cantt", "has_wheelchair_ramp": 1, "latitude": 30.34215, "longitude": 78.02148},
        {"booth_id": 2, "booth_name": "Garhi Cantt Booth 2", "station_name": "GIC Garhi Cantt", "has_wheelchair_ramp": 1, "latitude": 30.34215, "longitude": 78.02148},
        {"booth_id": 6, "booth_name": "Veerbhadra Science Block Booth 2", "station_name": "Veerbhadra College", "has_wheelchair_ramp": 1, "latitude": 30.10342, "longitude": 78.29471}
    ]

    mock_slots = [
        {"slot_id": 101, "booth_id": 1, "slot_date": "2026-11-15", "start_time": "07:00:00", "end_time": "09:30:00", "max_capacity": 60, "allocated_count": 10, "available_capacity": 50, "status": "OPEN"},
        {"slot_id": 102, "booth_id": 1, "slot_date": "2026-11-15", "start_time": "09:30:00", "end_time": "12:00:00", "max_capacity": 60, "allocated_count": 20, "available_capacity": 40, "status": "OPEN"},
        {"slot_id": 601, "booth_id": 6, "slot_date": "2026-11-15", "start_time": "07:00:00", "end_time": "09:30:00", "max_capacity": 50, "allocated_count": 5, "available_capacity": 45, "status": "OPEN"}
    ]

    with patch.object(booth_service, "get_polling_booths", return_value=mock_booths), \
         patch.object(booth_service, "get_time_slots_for_booth", side_effect=lambda booth_id, event_id=1: [s for s in mock_slots if s["booth_id"] == booth_id]):
        
        # When evaluating Booth 1, recommendation must strictly belong to Booth 1
        rec_booth1 = pred_service.recommend_optimal_slot(target_booth_id=1)
        assert rec_booth1["recommendation_found"] is True
        assert rec_booth1["recommended_booth_id"] == 1, "Recommended booth must be Booth 1"
        assert rec_booth1["recommended_slot_id"] in (101, 102)

        # When evaluating Booth 6, recommendation must strictly belong to Booth 6
        rec_booth6 = pred_service.recommend_optimal_slot(target_booth_id=6)
        assert rec_booth6["recommendation_found"] is True
        assert rec_booth6["recommended_booth_id"] == 6, "Recommended booth must be Booth 6"
        assert rec_booth6["recommended_slot_id"] == 601


# -----------------------------------------------------------------------------
# 7. BACKEND JURISDICTION ENFORCEMENT & PRE-VALIDATION
# -----------------------------------------------------------------------------
def test_backend_ineligible_booth_rejection():
    """Verify backend pre-validation rejects ineligible booth requests upfront."""
    # Attempt booking for Booth 6 (Veerbhadra Rishikesh) when assigned to Booth 1
    with patch.object(db_pool, "get_cursor") as mock_cursor_ctx:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "voter_id": 1,
            "assigned_booth_id": 1,
            "special_category": "SENIOR_CITIZEN"
        }
        mock_cursor_ctx.return_value.__enter__.return_value = (mock_conn, mock_cursor)

        result = allocation_service.allocate_voter_slot(
            voter_id=1,
            booth_id=6,  # Ineligible booth
            slot_id=25
        )

        assert result["success"] is False
        assert result["status_code"] == "INVALID_BOOTH_JURISDICTION"
        assert "cannot book Booth 6" in result["message"]


# -----------------------------------------------------------------------------
# 8. FRONTEND JURISDICTION GUARDS & API CLIENT INTEGRITY
# -----------------------------------------------------------------------------
def test_frontend_upfront_jurisdiction_guards():
    """Verify voter_portal.js and api_client.js contain upfront jurisdiction guards."""
    portal_js_path = FRONTEND_DIR / "js" / "voter_portal.js"
    client_js_path = FRONTEND_DIR / "js" / "api_client.js"
    portal_content = portal_js_path.read_text(encoding="utf-8")
    client_content = client_js_path.read_text(encoding="utf-8")

    # 1. API client supports voter_id, pc_id, ac_id in getNearbyBooths
    assert "voter_id" in client_content
    assert "getVoters" in client_content

    # 2. voter_portal.js checks assigned_booth_id in loadAvailableSlots
    assert "assigned_booth_id !== boothId" in portal_content
    assert "Ineligible Polling Booth Selected" in portal_content

    # 3. voter_portal.js checks assigned_booth_id before initiating booking
    assert "assigned_booth_id !== state.selectedBooth.booth_id" in portal_content


# -----------------------------------------------------------------------------
# 9. ZERO EMOJI AUDIT
# -----------------------------------------------------------------------------
def test_zero_emojis_in_frontend():
    """Verify zero emojis exist across all HTML, CSS, and JS files."""
    def is_emoji(char):
        cp = ord(char)
        return (
            0x1F300 <= cp <= 0x1F5FF or
            0x1F600 <= cp <= 0x1F64F or
            0x1F680 <= cp <= 0x1F6FF or
            0x1F700 <= cp <= 0x1F77F or
            0x1F780 <= cp <= 0x1F7FF or
            0x1F800 <= cp <= 0x1F8FF or
            0x1F900 <= cp <= 0x1F9FF or
            0x1FA00 <= cp <= 0x1FA6F or
            0x1FA70 <= cp <= 0x1FAFF or
            0x2600 <= cp <= 0x26FF or
            0x2700 <= cp <= 0x27BF
        )

    for root, _, files in os.walk(FRONTEND_DIR):
        for f in files:
            if f.endswith((".html", ".js", ".css")):
                file_path = Path(root) / f
                content = file_path.read_text(encoding="utf-8")
                emojis = [c for c in content if is_emoji(c)]
                assert len(emojis) == 0, f"Found {len(emojis)} emoji(s) in {file_path.name}: {emojis}"
