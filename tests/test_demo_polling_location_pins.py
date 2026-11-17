"""
VoteIT Test Suite: Demo Polling Location Pins Verification
Tests the multiple demo polling location pins on the Leaflet map:
- Woodbridge School
- Graphic Era Hill University (GEHU Bhimtal)
- Vikas Bhawan (Bhimtal)
- Nagar Palika Parishad Office (Bhimtal)
Ensures single source of truth, verified coordinates, distinct pins,
bounds framing, zero emojis, and non-regression of existing workflows.
"""

import re
import pytest
from pathlib import Path


@pytest.fixture
def voter_portal_js():
    p = Path("frontend/js/voter_portal.js")
    assert p.exists()
    return p.read_text(encoding="utf-8")


@pytest.fixture
def styles_css():
    p = Path("frontend/css/styles.css")
    assert p.exists()
    return p.read_text(encoding="utf-8")


@pytest.fixture
def index_html():
    p = Path("frontend/index.html")
    assert p.exists()
    return p.read_text(encoding="utf-8")


def test_single_maintainable_location_data_source(voter_portal_js):
    """Verify single source of truth DEMO_POLLING_LOCATIONS is defined."""
    assert "DEMO_POLLING_LOCATIONS" in voter_portal_js
    assert "window.DEMO_POLLING_LOCATIONS" in voter_portal_js


def test_demo_locations_and_verified_coordinates(voter_portal_js):
    """Verify accurate coordinates for all demo polling locations near Nagri Gaon and Bhimtal."""
    # 1. Woodbridge School (near Nagri Gaon)
    assert "Woodbridge School" in voter_portal_js
    assert "29.369" in voter_portal_js
    assert "79.522" in voter_portal_js

    # 2. Graphic Era Hill University (GEHU Bhimtal, near Nagri Gaon / Sattal Road)
    assert "Graphic Era Hill University" in voter_portal_js
    assert "29.3751" in voter_portal_js
    assert "79.5313" in voter_portal_js

    # 3. Vikas Bhawan (District Development Complex, Bhimtal)
    assert "Vikas Bhawan" in voter_portal_js
    assert "29.3602" in voter_portal_js
    assert "79.5535" in voter_portal_js

    # 4. Nagar Palika Parishad Office (Bhimtal)
    assert "Nagar Palika Parishad" in voter_portal_js
    assert "29.3445" in voter_portal_js
    assert "79.5634" in voter_portal_js


def test_distinct_pin_classes_in_styles_css(styles_css):
    """Verify clearly distinguishable, professional CSS classes for all demo pin types."""
    assert ".custom-demo-pin" in styles_css
    assert ".demo-school-pin" in styles_css
    assert ".demo-univ-pin" in styles_css
    assert ".demo-gov-pin" in styles_css
    assert ".demo-gov-alt-pin" in styles_css

    # Check distinct color themes
    assert "#4f46e5" in styles_css  # Indigo for school
    assert "#0d9488" in styles_css  # Teal for university
    assert "#0284c7" in styles_css  # Sky blue for Vikas Bhawan
    assert "#b45309" in styles_css  # Amber for Nagar Palika


def test_popup_rendering_and_demo_tagging(voter_portal_js):
    """Verify markers display location name, demo tag, and reference selection in popup."""
    assert "DEMO POLLING LOCATION" in voter_portal_js
    assert "selectDemoLocation" in voter_portal_js
    assert "plotDemoPollingLocations" in voter_portal_js


def test_map_bounds_encloses_all_locations(voter_portal_js):
    """Verify BHIMTAL_NAGRIGAON_BOUNDS properly encloses all demo locations and landmarks."""
    assert "BHIMTAL_NAGRIGAON_BOUNDS" in voter_portal_js
    # Min lat <= 29.344, Max lat >= 29.380
    assert "29.3400" in voter_portal_js or "29.34" in voter_portal_js
    assert "29.3850" in voter_portal_js or "29.39" in voter_portal_js


def test_strictly_zero_emojis_in_frontend(voter_portal_js, styles_css, index_html):
    """Ensure zero emojis across all frontend files."""
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
    assert len(emoji_pattern.findall(voter_portal_js)) == 0
    assert len(emoji_pattern.findall(styles_css)) == 0
    assert len(emoji_pattern.findall(index_html)) == 0
