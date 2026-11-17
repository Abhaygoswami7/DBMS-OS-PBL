"""
Automated Regression Tests for UI Consistency and Slot Selection Logic.

Verifies:
1. Elimination of "located 0.0 km away" in crowd prediction service.
2. Distinct distance phrasing for registered station reference vs live GPS.
3. API route /api/slots/available query parameter handling (lat, lon).
4. Frontend index.html and styles.css distinction between selected and recommended slots.
5. Strict zero-emoji compliance.
"""

import pytest
import re
from pathlib import Path
from backend.app.services.crowd_prediction_service import crowd_prediction_service
from backend.app import create_app


def test_recommendation_wording_registered_station_reference():
    """Verify that when using registered station coordinates, wording clearly states registered reference."""
    # Voter 1 (Ramesh Chandra Sharma, assigned to Booth 1)
    rec = crowd_prediction_service.recommend_optimal_slot(
        voter_id=1,
        target_booth_id=1,
        lat=29.3751,
        lon=79.5313
    )
    assert rec["recommendation_found"] is True
    reason = rec["recommendation_reason"]

    # Must NEVER say "located 0.0 km away" or "0.0 km"
    assert "0.0 km away" not in reason
    assert "located 0.0 km" not in reason

    # Must contain clear reference wording
    assert "at the registered polling station (measured from registered station reference)" in reason


def test_recommendation_wording_device_gps_preset():
    """Verify that when using distinct device/preset GPS coordinates, distance is explicitly tagged from GPS."""
    # Coords away from station (e.g. Rajpur Road preset 30.3398, 78.0487)
    rec = crowd_prediction_service.recommend_optimal_slot(
        voter_id=1,
        target_booth_id=1,
        lat=30.3398,
        lon=78.0487
    )
    assert rec["recommendation_found"] is True
    reason = rec["recommendation_reason"]

    # Must NEVER say "located 0.0 km away"
    assert "0.0 km away" not in reason

    # Must state distance from current GPS location
    assert "km from your current GPS location" in reason


def test_api_slots_available_with_gps_params():
    """Verify /api/slots/available handles lat and lon parameters."""
    app = create_app()
    client = app.test_client()

    # Call with lat/lon preset
    res = client.get("/api/slots/available?booth_id=1&voter_id=1&lat=30.3398&lon=78.0487")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    rec = data.get("recommendation", {})
    reason = rec.get("recommendation_reason", "")

    assert "0.0 km away" not in reason
    assert "km from your current GPS location" in reason


def test_styles_css_visual_distinction_classes():
    """Verify that styles.css defines separate visual styles for recommended and selected slot cards."""
    styles_path = Path("frontend/css/styles.css")
    assert styles_path.exists()
    content = styles_path.read_text(encoding="utf-8")

    # Verify .selected-ribbon exists and uses navy color
    assert ".selected-ribbon" in content
    assert "--irctc-navy-primary" in content

    # Verify .slot-card.selected uses navy border
    assert ".slot-card.selected" in content

    # Verify .slot-card.recommended uses orange styling
    assert ".slot-card.recommended" in content

    # Verify .slot-selection-status-banner exists
    assert ".slot-selection-status-banner" in content
    assert ".slot-selection-badge-custom" in content
    assert ".slot-selection-badge-matched" in content


def test_index_html_slot_status_banner_present():
    """Verify index.html contains the slot selection comparison banner."""
    html_path = Path("frontend/index.html")
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")

    assert 'id="slotSelectionStatusBanner"' in content
    assert 'id="slotSelectionStatusText"' in content
    assert 'id="slotSelectionStatusBadge"' in content


def test_zero_emojis_in_updated_files():
    """Ensure zero emojis are present across all updated frontend files."""
    emoji_regex = re.compile(
        r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\ud83c-\ud83e][\ud000-\udfff]',
        flags=re.UNICODE
    )
    files_to_check = [
        "frontend/index.html",
        "frontend/css/styles.css",
        "frontend/js/api_client.js",
        "frontend/js/voter_portal.js",
    ]
    for file_name in files_to_check:
        content = Path(file_name).read_text(encoding="utf-8")
        matches = emoji_regex.findall(content)
        assert len(matches) == 0, f"Found emojis in {file_name}: {matches}"
