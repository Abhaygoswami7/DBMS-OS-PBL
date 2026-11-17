"""
Interactive Polling Location Selection & Leaflet Map Synchronization Test Suite
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)

Verifies:
  1. Synchronized selection between the left-hand station list and the Leaflet map.
  2. Automatic smooth panning and zooming to zoom ~16.5 on station selection.
  3. Visual prominence and pulsing animation for the selected location marker (.station-pin-selected).
  4. Display of location name in popups/tooltips and subtle location indicator banner.
  5. Support for all 4 authentic demonstration locations:
     - Graphic Era Hill University, Bhimtal Campus (29.3751, 79.5313)
     - Woodbridge School (29.3690, 79.5220)
     - Vikas Bhawan, Bhimtal (29.3602, 79.5535)
     - Nagar Palika Parishad Office, Bhimtal (29.3445, 79.5634)
  6. Reverse interaction: Clicking map markers triggers selection and synchronizes the station list.
  7. Reset view / fit all four markers when no location is selected.
  8. Zero emojis across all modified frontend files.
"""

import re
import pytest
from backend.app import create_app
from backend.app.services.booth_service import booth_service


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_html_contains_interactive_elements():
    """Verify index.html contains the map container, indicator, and reset button."""
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert 'id="boothMap"' in html
    assert 'id="selectedStationIndicator"' in html
    assert 'id="indicatorStationName"' in html
    assert 'id="btnResetMapView"' in html

    # Verify preset buttons for all 4 locations
    assert 'id="presetGehuBhimtal"' in html
    assert 'id="presetWoodbridge"' in html
    assert 'id="presetVikasBhawan"' in html
    assert 'id="presetNagarPalika"' in html


def test_css_contains_pulsing_animation_and_prominent_highlight():
    """Verify styles.css implements pulsing keyframes and enhanced marker styling."""
    with open("frontend/css/styles.css", "r", encoding="utf-8") as f:
        css = f.read()

    assert ".station-pin-selected" in css
    assert "stationPinPulse" in css
    assert "@keyframes stationPinPulse" in css
    assert "scale(1.35)" in css
    assert ".selected-station-indicator" in css
    assert ".btn-indicator-reset" in css


def test_js_implements_interactive_controller_and_reverse_sync():
    """Verify voter_portal.js defines selectPollingStation, resetMapSelection, and marker click handlers."""
    with open("frontend/js/voter_portal.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "function selectPollingStation" in js
    assert "function resetMapSelection" in js
    assert "function updateSelectedLocationIndicator" in js
    assert "window.selectPollingStation = selectPollingStation" in js
    assert "window.resetMapSelection = resetMapSelection" in js

    # Smooth flyTo with zoom ~16.5
    assert "zoomLevel: 16.5" in js
    assert "state.map.flyTo([lat, lon], opts.zoomLevel" in js

    # Reverse interaction: marker click triggers selection
    assert 'marker.on("click"' in js
    assert "selectPollingStation(stn.station_id" in js

    # Reset view fits all 4 markers
    assert "state.map.fitBounds(BHIMTAL_NAGRIGAON_BOUNDS" in js

    # Synchronizes card in left list
    assert 'c.classList.add("selected")' in js
    assert 'c.scrollIntoView({ behavior: "smooth", block: "nearest" })' in js


def test_all_four_locations_active_and_distinct_in_backend(client):
    """Verify backend provides all 4 authentic demonstration locations with distinct coordinates."""
    res = client.get("/api/booths/nearby?lat=29.3650&lon=79.5328")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    stations = {}
    for b in data["booths"]:
        s_id = b["station_id"]
        if s_id not in stations:
            stations[s_id] = {
                "name": b["station_name"],
                "lat": float(b["latitude"]),
                "lon": float(b["longitude"])
            }

    assert len(stations) == 4

    names = [s["name"] for s in stations.values()]
    assert any("Graphic Era Hill University" in n for n in names)
    assert any("Woodbridge School" in n for n in names)
    assert any("Vikas Bhawan" in n for n in names)
    assert any("Nagar Palika" in n for n in names)

    # Verify coordinates match Bhimtal/Nagri Gaon
    gehu = next(s for s in stations.values() if "Graphic Era" in s["name"])
    assert abs(gehu["lat"] - 29.3751) < 0.001
    assert abs(gehu["lon"] - 79.5313) < 0.001

    woodbridge = next(s for s in stations.values() if "Woodbridge" in s["name"])
    assert abs(woodbridge["lat"] - 29.3690) < 0.001
    assert abs(woodbridge["lon"] - 79.5220) < 0.001

    vikas = next(s for s in stations.values() if "Vikas Bhawan" in s["name"])
    assert abs(vikas["lat"] - 29.3602) < 0.001
    assert abs(vikas["lon"] - 79.5535) < 0.001

    palika = next(s for s in stations.values() if "Nagar Palika" in s["name"])
    assert abs(palika["lat"] - 29.3445) < 0.001
    assert abs(palika["lon"] - 79.5634) < 0.001


def test_strictly_zero_emojis():
    """Verify zero emojis in all modified UI files."""
    emoji_regex = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
    files = ["frontend/index.html", "frontend/js/voter_portal.js", "frontend/css/styles.css"]
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        matches = emoji_regex.findall(content)
        assert len(matches) == 0, f"Found emojis in {path}: {matches}"
