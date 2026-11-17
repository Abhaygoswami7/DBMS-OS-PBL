"""
VoteIT Test Suite: Bhimtal and Nagri Gaon Map Location Verification
Verifies Leaflet map focus, verified geographical coordinates, custom markers,
labels, popups, and non-regression on dynamic polling booths and step navigation.
"""

import re
import pytest
from pathlib import Path


@pytest.fixture
def voter_portal_js():
    p = Path("frontend/js/voter_portal.js")
    assert p.exists(), "frontend/js/voter_portal.js must exist"
    return p.read_text(encoding="utf-8")


@pytest.fixture
def styles_css():
    p = Path("frontend/css/styles.css")
    assert p.exists(), "frontend/css/styles.css must exist"
    return p.read_text(encoding="utf-8")


@pytest.fixture
def index_html():
    p = Path("frontend/index.html")
    assert p.exists(), "frontend/index.html must exist"
    return p.read_text(encoding="utf-8")


def test_bhimtal_and_nagrigaon_coordinates_defined(voter_portal_js):
    """Verify exact accurate verified coordinates are defined for Bhimtal and Nagri Gaon."""
    # Bhimtal: 29.3500, 79.5535
    assert "29.35" in voter_portal_js, "Bhimtal latitude 29.3500 must be in voter_portal.js"
    assert "79.5535" in voter_portal_js, "Bhimtal longitude 79.5535 must be in voter_portal.js"
    
    # Nagri Gaon: 29.3800, 79.5121
    assert "29.38" in voter_portal_js, "Nagri Gaon latitude 29.3800 must be in voter_portal.js"
    assert "79.5121" in voter_portal_js, "Nagri Gaon longitude 79.5121 must be in voter_portal.js"

    # Constants presence
    assert "BHIMTAL_COORDS" in voter_portal_js, "BHIMTAL_COORDS constant must be defined"
    assert "NAGRI_GAON_COORDS" in voter_portal_js, "NAGRI_GAON_COORDS constant must be defined"
    assert "BHIMTAL_NAGRIGAON_BOUNDS" in voter_portal_js, "BHIMTAL_NAGRIGAON_BOUNDS constant must be defined"


def test_map_initialization_focuses_bhimtal_nagrigaon(voter_portal_js):
    """Verify ensureMapInitialized initializes centered and bounded around Bhimtal and Nagri Gaon."""
    assert "BHIMTAL_NAGRIGAON_CENTER" in voter_portal_js
    assert "center: BHIMTAL_NAGRIGAON_CENTER" in voter_portal_js or "BHIMTAL_NAGRIGAON_CENTER" in voter_portal_js
    assert "BHIMTAL_NAGRIGAON_BOUNDS" in voter_portal_js
    assert "plotBhimtalAndNagriGaonMarkers" in voter_portal_js


def test_distinguishable_marker_icons_and_classes(voter_portal_js, styles_css):
    """Verify distinct custom pins for Bhimtal and Nagri Gaon in both JS and CSS."""
    # JS functions
    assert "getBhimtalMarkerIcon" in voter_portal_js
    assert "getNagriGaonMarkerIcon" in voter_portal_js

    # CSS classes
    assert ".custom-bhimtal-pin" in styles_css
    assert ".custom-nagrigaon-pin" in styles_css
    assert ".map-location-label" in styles_css

    # Check distinct visual styling (colors)
    assert "#0284c7" in styles_css, "Sky blue / cyan color for Bhimtal pin"
    assert "#16a34a" in styles_css, "Emerald green color for Nagri Gaon pin"


def test_labels_and_popups_for_both_locations(voter_portal_js):
    """Verify permanent tooltips and rich popups identify both Bhimtal and Nagri Gaon."""
    assert 'bindTooltip("Bhimtal"' in voter_portal_js
    assert 'bindTooltip("Nagri Gaon"' in voter_portal_js
    assert "permanent: true" in voter_portal_js

    assert "Bhimtal, Nainital District" in voter_portal_js
    assert "Nagri Gaon, Nainital District" in voter_portal_js


def test_leaflet_interactive_map_and_tiles_preserved(voter_portal_js, index_html):
    """Verify Leaflet map container, OpenStreetMap tiles and CartoDB fallback are preserved."""
    assert 'id="boothMap"' in index_html
    assert "tile.openstreetmap.org" in voter_portal_js
    assert "cartocdn.com" in voter_portal_js
    assert "scrollWheelZoom: true" in voter_portal_js
    assert "zoomControl: true" in voter_portal_js


def test_dynamic_polling_station_markers_preserved(voter_portal_js):
    """Verify dynamic polling booth station markers, wheelchair badges, and flyTo selection remain intact."""
    assert "getStationMarkerIcon" in voter_portal_js
    assert "flyTo" in voter_portal_js
    assert "selectBoothFromMap" in voter_portal_js
    assert "has_wheelchair_ramp" in voter_portal_js


def test_step_navigation_preserves_bhimtal_focus(voter_portal_js):
    """Verify step transitions trigger map invalidation and maintain Bhimtal & Nagri Gaon bounds."""
    assert "triggerMapInvalidate" in voter_portal_js
    assert "BHIMTAL_NAGRIGAON_BOUNDS" in voter_portal_js
    assert "goToStep" in voter_portal_js


def test_strictly_zero_emojis_in_frontend(voter_portal_js, styles_css, index_html):
    """Verify strictly zero emojis in all frontend codebase."""
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
    assert len(emoji_pattern.findall(voter_portal_js)) == 0, "No emojis in voter_portal.js"
    assert len(emoji_pattern.findall(styles_css)) == 0, "No emojis in styles.css"
    assert len(emoji_pattern.findall(index_html)) == 0, "No emojis in index.html"
