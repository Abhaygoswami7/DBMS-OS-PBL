"""
Targeted Verification Suite: Bhimtal and Nagri Gaon Active Selectable Polling Stations
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)

Verifies:
  1. The 4 demonstration polling stations in Bhimtal and Nagri Gaon are the actual, active database records:
     - Graphic Era Hill University, Bhimtal Campus (29.3751, 79.5313)
     - Woodbridge School (29.3690, 79.5220)
     - Vikas Bhawan (District Development Complex) (29.3602, 79.5535)
     - Nagar Palika Parishad Office, Bhimtal (29.3445, 79.5634)
  2. Zero old Garhi Cantt / Dehradun stations or booths exist in active demonstration queries.
  3. All 8 booths are nested under Nainital-Udhamsingh Nagar PC (id 2) and Bhimtal AC (id 3).
  4. Voter profiles for each station/booth return correct station names, addresses, and coordinates.
  5. Atomic slot allocation on new demonstration booths generates correct ERS slips with Bhimtal/Nagri Gaon data.
  6. Frontend index.html and voter_portal.js contain zero emojis.
"""

import re
import pytest
from backend.app import create_app
from database.db_pool import db_pool
from backend.app.services.booth_service import booth_service
from backend.app.services.voter_service import voter_service
from backend.app.services.allocation_service import allocation_service


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_four_bhimtal_stations_in_database():
    """Verify the 4 exact Bhimtal/Nagri Gaon stations exist in database with correct coordinates."""
    stations = booth_service.get_polling_stations()
    assert len(stations) == 4

    station_names = [s["station_name"] for s in stations]
    assert "Graphic Era Hill University, Bhimtal Campus" in station_names
    assert "Woodbridge School" in station_names
    assert "Vikas Bhawan (District Development Complex)" in station_names
    assert "Nagar Palika Parishad Office, Bhimtal" in station_names

    # Check coordinates
    gehu = next(s for s in stations if "Graphic Era" in s["station_name"])
    assert abs(gehu["latitude"] - 29.3751) < 0.0005
    assert abs(gehu["longitude"] - 79.5313) < 0.0005
    assert gehu["pincode"] == "263136"

    woodbridge = next(s for s in stations if "Woodbridge" in s["station_name"])
    assert abs(woodbridge["latitude"] - 29.3690) < 0.0005
    assert abs(woodbridge["longitude"] - 79.5220) < 0.0005
    assert woodbridge["pincode"] == "263132"

    vikas = next(s for s in stations if "Vikas Bhawan" in s["station_name"])
    assert abs(vikas["latitude"] - 29.3602) < 0.0005
    assert abs(vikas["longitude"] - 79.5535) < 0.0005
    assert vikas["pincode"] == "263136"

    palika = next(s for s in stations if "Nagar Palika" in s["station_name"])
    assert abs(palika["latitude"] - 29.3445) < 0.0005
    assert abs(palika["longitude"] - 79.5634) < 0.0005
    assert palika["pincode"] == "263136"


def test_no_legacy_garhi_cantt_stations():
    """Verify old Garhi Cantt / Dehradun stations are completely absent from active stations."""
    stations = booth_service.get_polling_stations()
    for s in stations:
        assert "Garhi Cantt" not in s["station_name"]
        assert "Hathibarkala" not in s["station_name"]
        assert "Punjab Sind" not in s["station_name"]
        assert "Delhi Public School" not in s["station_name"]


def test_all_booths_under_bhimtal_ac_and_nainital_pc():
    """Verify all 8 booths map to Nainital-Udhamsingh Nagar PC and Bhimtal AC."""
    booths = booth_service.get_polling_booths()
    assert len(booths) == 8

    for b in booths:
        assert b["pc_id"] == 2
        assert b["ac_id"] == 3
        assert b["parliamentary_constituency"] == "Nainital-Udhamsingh Nagar Parliamentary Constituency"
        assert b["assembly_constituency"] == "Bhimtal Assembly Constituency"


def test_api_nearby_booths_returns_bhimtal_stations(client):
    """Verify GET /api/booths/nearby returns the 4 Bhimtal/Nagri Gaon stations."""
    res = client.get("/api/booths/nearby?lat=29.3650&lon=79.5328")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["total_booths_found"] == 8

    station_names = set(b["station_name"] for b in data["booths"])
    assert len(station_names) == 4
    assert "Graphic Era Hill University, Bhimtal Campus" in station_names
    assert "Woodbridge School" in station_names
    assert "Vikas Bhawan (District Development Complex)" in station_names
    assert "Nagar Palika Parishad Office, Bhimtal" in station_names


def test_voter_profiles_mapped_to_bhimtal_stations():
    """Verify voters assigned to each of the 4 stations retrieve accurate Bhimtal details."""
    # Voter 7 -> Booth 1 (GEHU)
    v7 = voter_service.get_voter_by_demo_epic("DEM-UK-2026-0007")
    assert v7["assigned_booth_id"] == 1
    assert v7["station_name"] == "Graphic Era Hill University, Bhimtal Campus"
    assert v7["pincode"] == "263136"

    # Voter 20 -> Booth 3 (Woodbridge School, Nagri Gaon)
    v20 = voter_service.get_voter_by_demo_epic("DEM-UK-2026-0020")
    assert v20["assigned_booth_id"] == 3
    assert v20["station_name"] == "Woodbridge School"
    assert v20["pincode"] == "263132"

    # Voter 34 -> Booth 5 (Vikas Bhawan)
    v34 = voter_service.get_voter_by_demo_epic("DEM-UK-2026-0034")
    assert v34["assigned_booth_id"] == 5
    assert v34["station_name"] == "Vikas Bhawan (District Development Complex)"
    assert v34["pincode"] == "263136"

    # Voter 51 -> Booth 7 (Nagar Palika Parishad)
    v51 = voter_service.get_voter_by_demo_epic("DEM-UK-2026-0051")
    assert v51["assigned_booth_id"] == 7
    assert v51["station_name"] == "Nagar Palika Parishad Office, Bhimtal"
    assert v51["pincode"] == "263136"


def test_atomic_booking_at_woodbridge_school():
    """Verify end-to-end atomic booking for a voter at Woodbridge School (Nagri Gaon)."""
    # Voter 23 (Ashok Kumar Badoni, assigned to Booth 3)
    voter_id = 23
    booth_id = 3
    slot_id = 11  # Afternoon Slot

    # Clean up prior booking if any
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute("UPDATE slot_allocations SET status = 'CANCELLED' WHERE voter_id = %s AND status = 'CONFIRMED'", (voter_id,))
        conn.commit()

    alloc_res = allocation_service.allocate_voter_slot(
        voter_id=voter_id,
        booth_id=booth_id,
        slot_id=slot_id,
        allocation_type="USER_RESERVED"
    )
    assert alloc_res["success"] is True
    assert alloc_res["status_code"] == "SUCCESS"
    token = alloc_res["booking_reference_token"]

    slip = allocation_service.get_voter_appointment_slip(booking_reference_token=token)
    assert slip is not None
    assert slip["station_name"] == "Woodbridge School"
    assert "Dob, Lewshal" in slip["station_address"]
    assert slip["assembly_constituency"] == "Bhimtal Assembly Constituency"

    # Cancel and clean up
    cancel_res = allocation_service.cancel_slot_allocation(booking_reference_token=token)
    assert cancel_res["success"] is True


def test_zero_emojis_in_frontend():
    """Ensure zero emojis across frontend HTML and JS files."""
    emoji_regex = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)

    for path in ["frontend/index.html", "frontend/js/voter_portal.js"]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        matches = emoji_regex.findall(content)
        assert len(matches) == 0, f"Found emojis in {path}: {matches}"
