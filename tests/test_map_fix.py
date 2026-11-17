"""
Unit & Regression Tests for Polling Station Geo-Locator & Route Map Fix
Project: VoteIT — Smart Polling Booth & Time-Slot Allocation Platform (ONOE)
Module: tests/test_map_fix.py

Verifies:
  1. Leaflet CDN tags (primary + fallback) in index.html.
  2. Map container elements (#boothMap, #mapOfflineFallback) in index.html.
  3. CSS map rules, custom SVG pins, popup styles in styles.css.
  4. JavaScript map lifecycle, real coordinates (no Math.random), fitBounds, and ResizeObserver in voter_portal.js.
  5. Station coordinates integrity in seed_data.sql.
  6. Zero-emoji compliance across all frontend files.
"""

import os
import re
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"

def test_index_html_map_imports_and_containers():
    """Verify Leaflet imports and map container structure in index.html."""
    index_path = FRONTEND_DIR / "index.html"
    assert index_path.exists(), "index.html must exist"
    content = index_path.read_text(encoding="utf-8")

    # Leaflet CSS and JS
    assert "leaflet.css" in content, "Leaflet CSS must be imported"
    assert "leaflet.js" in content, "Leaflet JS must be imported"
    assert "cdnjs.cloudflare.com/ajax/libs/leaflet" in content, "CDN fallback must be present"

    # Map container and offline fallback
    assert 'id="boothMap"' in content, "boothMap container must exist in index.html"
    assert 'id="mapOfflineFallback"' in content, "mapOfflineFallback element must exist in index.html"
    assert "POLLING STATION GEO-LOCATOR & ROUTE MAP" in content, "Card title must be intact"


def test_styles_css_map_and_pin_classes():
    """Verify map container dimensions and custom SVG marker styles in styles.css."""
    css_path = FRONTEND_DIR / "css" / "styles.css"
    assert css_path.exists(), "styles.css must exist"
    content = css_path.read_text(encoding="utf-8")

    # Map container dimensions
    assert "#boothMap" in content, "#boothMap must be styled"
    assert "height: 380px" in content, "Map must have 380px height"
    assert "min-height: 380px" in content, "Map must have min-height"
    assert ".leaflet-container" in content, ".leaflet-container must be styled"

    # Custom SVG Pin styling
    assert ".custom-station-pin" in content, "custom-station-pin class must be defined"
    assert ".station-pin-selected" in content, "station-pin-selected class must be defined"
    assert ".station-ramp-badge" in content, "station-ramp-badge class must be defined"
    assert ".custom-voter-pin" in content, "custom-voter-pin class must be defined"
    assert ".voter-radar-ring" in content, "voter-radar-ring class must be defined"
    assert ".leaflet-popup-content-wrapper" in content, "leaflet-popup-content-wrapper must be styled"


def test_voter_portal_map_logic():
    """Verify JavaScript map controller, sizing triggers, and coordinate handling."""
    js_path = FRONTEND_DIR / "js" / "voter_portal.js"
    assert js_path.exists(), "voter_portal.js must exist"
    content = js_path.read_text(encoding="utf-8")

    # Map initialization and lifecycle
    assert "ensureMapInitialized" in content, "ensureMapInitialized function must exist"
    assert "triggerMapInvalidate" in content, "triggerMapInvalidate helper must exist"
    assert "initOrUpdateMap" in content, "initOrUpdateMap function must exist"

    # Tile providers
    assert "tile.openstreetmap.org" in content, "OpenStreetMap tile layer must be configured"
    assert "cartocdn.com" in content, "CartoDB fallback tile layer must be configured"

    # Real coordinates: Ensure Math.random() is NOT used for coordinates inside map logic
    map_func_match = re.search(r"function initOrUpdateMap\(.*?\)\s*\{(.*?)\n  \}", content, re.DOTALL)
    assert map_func_match, "initOrUpdateMap implementation must be present"
    assert "Math.random" not in map_func_match.group(1), "Fake coordinate jitter (Math.random) must NOT be present in initOrUpdateMap"

    # Bounds fitting and selection interaction
    assert "fitBounds" in content, "state.map.fitBounds must be called to frame all stations"
    assert "window.selectBoothFromMap" in content, "window.selectBoothFromMap must be exported for popups"
    assert "flyTo" in content, "Map flyTo animation on booth selection must exist"

    # Sizing resilience
    assert "ResizeObserver" in content, "ResizeObserver must be used for dynamic layout updates"
    assert "invalidateSize" in content, "invalidateSize must be called"


def test_seed_data_station_coordinates():
    """Verify that all polling stations have valid real-world coordinates in Uttarakhand."""
    seed_path = ROOT_DIR / "database" / "seed_data.sql"
    assert seed_path.exists(), "seed_data.sql must exist"
    content = seed_path.read_text(encoding="utf-8")

    # Match latitude and longitude inserts for polling stations
    matches = re.findall(r"'(STN-[A-Z]+-\d+)'[^;]+?([23]\d\.\d+)[,\s]+([78]\d\.\d+)", content)
    assert len(matches) >= 4, "Expected at least 4 seeded polling stations with coordinates"

    for stn_code, lat, lon in matches:
        lat_f = float(lat)
        lon_f = float(lon)
        # Uttarakhand latitude range: 28.7 to 31.5; longitude range: 77.5 to 81.1
        assert 28.5 <= lat_f <= 31.5, f"Station {stn_code} latitude {lat_f} must be in Uttarakhand range"
        assert 77.5 <= lon_f <= 81.5, f"Station {stn_code} longitude {lon_f} must be in Uttarakhand range"


def test_zero_emojis_in_frontend():
    """Verify zero emoji characters across all HTML, CSS, and JS files in frontend."""
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
            if f.endswith((".html", ".css", ".js")):
                fp = Path(root) / f
                text = fp.read_text(encoding="utf-8")
                emojis = [c for c in text if is_emoji(c)]
                assert len(emojis) == 0, f"Found {len(emojis)} emoji(s) in {f}: {emojis}"
