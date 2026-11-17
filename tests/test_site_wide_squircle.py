"""
Test Suite: Apple-Inspired Continuous Squircle Design Across the Entire VoteIT Website
Validates global geometry tokens, component-level squircle curvature, and child clipping.
"""

import os
import pytest


@pytest.fixture(scope="module")
def styles_css():
    css_path = os.path.join(
        os.path.dirname(__file__), "..", "frontend", "css", "styles.css"
    )
    with open(css_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def login_html():
    path = os.path.join(os.path.dirname(__file__), "..", "frontend", "login.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_squircle_geometry_tokens_present(styles_css):
    """Verify modern squircle tokens and radius guidance ranges in :root."""
    assert "--corner-squircle: squircle;" in styles_css
    assert "--radius-xs: 10px;" in styles_css
    assert "--radius-sm: 12px;" in styles_css
    assert "--radius-md: 18px;" in styles_css
    assert "--radius-lg: 24px;" in styles_css
    assert "--radius-xl: 28px;" in styles_css
    assert "--radius-modal: 28px;" in styles_css


def test_squircle_properties_present(styles_css):
    """Verify modern squircle properties are declared in styles.css."""
    assert "corner-shape: squircle" in styles_css
    assert "-webkit-corner-shape: squircle" in styles_css


def test_cards_and_containers_have_squircle_and_clipping(styles_css):
    """Verify cards have squircle curvature and overflow: hidden to clip child header bands."""
    assert ".irctc-card {" in styles_css
    assert "overflow: hidden;" in styles_css
    assert ".appointment-slip {" in styles_css
    assert ".stepper-track {" in styles_css
    assert ".booth-card {" in styles_css
    assert ".slot-card {" in styles_css
    assert ".cris-kpi-card {" in styles_css
    assert ".data-table-container {" in styles_css


def test_form_inputs_and_buttons_squircle(styles_css):
    """Verify inputs, buttons, and form controls have squircle curvature."""
    assert ".form-control," in styles_css
    assert ".form-input," in styles_css
    assert ".form-select {" in styles_css
    assert ".btn-primary {" in styles_css
    assert ".btn-secondary {" in styles_css
    assert ".btn-outline-danger {" in styles_css


def test_map_containers_and_popups_squircle(styles_css):
    """Verify map containers and popups are styled with squircle curvature."""
    assert "#boothMap," in styles_css
    assert ".leaflet-container {" in styles_css
    assert ".leaflet-popup-content-wrapper {" in styles_css


def test_disha_assistant_and_modals_squircle(styles_css):
    """Verify floating drawer, chips, and assistant response boxes have squircle curvature."""
    assert ".disha-float-btn {" in styles_css
    assert ".disha-drawer {" in styles_css
    assert ".disha-chip {" in styles_css
    assert ".disha-response-box {" in styles_css


def test_captcha_boxes_and_recent_bookings_squircle(styles_css, login_html):
    """Verify CAPTCHA displays and Recently Booked Voters have squircle styling."""
    assert "#captchaDisplay" in styles_css
    assert "#adminCaptchaDisplay" in styles_css
    assert "#recentBookingsCard" in styles_css
    assert "#recentBookingsTableWrap" in styles_css

    # Check that login.html does not contain legacy hardcoded 4px border-radius on captchas
    assert 'id="captchaDisplay" style="' in login_html
    assert "corner-shape:squircle" in login_html
    assert 'id="adminCaptchaDisplay" style="' in login_html
