"""
Tests for:
  - GET /api/admin/recent-bookings (admin-protected, paginated)
  - Login page voter panel: CAPTCHA + OTP field presence
  - Login page CSS: glassmorphism removed, solid white card
"""

import pytest
import sys
import os

# Allow importing backend modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# TASK 1: Recent Bookings API
# ---------------------------------------------------------------------------

class TestRecentBookingsEndpoint:
    """Tests for GET /api/admin/recent-bookings"""

    @pytest.fixture(scope="class")
    def app(self):
        from backend.app import create_app
        application = create_app()
        application.config["TESTING"] = True
        return application

    @pytest.fixture(scope="class")
    def client(self, app):
        with app.test_client() as c:
            yield c

    @pytest.fixture(scope="class")
    def admin_token(self, client):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200, f"Admin login failed: {resp.get_data(as_text=True)}"
        return resp.get_json()["access_token"]

    def test_recent_bookings_no_auth_returns_401(self, client):
        resp = client.get("/api/admin/recent-bookings")
        assert resp.status_code == 401, (
            f"Expected 401 without token, got {resp.status_code}"
        )

    def test_recent_bookings_with_admin_token_returns_200(self, client, admin_token):
        resp = client.get(
            "/api/admin/recent-bookings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200, (
            f"Expected 200 with valid admin token, got {resp.status_code}: "
            f"{resp.get_data(as_text=True)}"
        )

    def test_recent_bookings_response_structure(self, client, admin_token):
        resp = client.get(
            "/api/admin/recent-bookings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = resp.get_json()
        assert data.get("success") is True
        assert "bookings" in data
        assert "total_count" in data
        assert "page_info" in data
        pi = data["page_info"]
        assert "limit" in pi
        assert "offset" in pi
        assert "returned" in pi
        assert "has_more" in pi

    def test_recent_bookings_default_limit_is_10(self, client, admin_token):
        resp = client.get(
            "/api/admin/recent-bookings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = resp.get_json()
        assert data["page_info"]["limit"] == 10

    def test_recent_bookings_custom_limit(self, client, admin_token):
        resp = client.get(
            "/api/admin/recent-bookings?limit=5&offset=0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["page_info"]["limit"] == 5
        assert data["page_info"]["offset"] == 0

    def test_recent_bookings_records_have_required_fields(self, client, admin_token):
        resp = client.get(
            "/api/admin/recent-bookings?limit=5",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = resp.get_json()
        bookings = data["bookings"]
        required_fields = [
            "allocation_id", "booking_reference_token", "allocation_status",
            "full_name", "demo_epic_no", "station_name", "booth_name",
            "booth_number", "slot_date", "start_time", "end_time",
            "event_name", "created_at", "special_category", "priority_level"
        ]
        for booking in bookings:
            for field in required_fields:
                assert field in booking, (
                    f"Required field '{field}' missing from booking record: {booking}"
                )

    def test_recent_bookings_does_not_expose_sensitive_data(self, client, admin_token):
        resp = client.get(
            "/api/admin/recent-bookings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = resp.get_json()
        raw = resp.get_data(as_text=True)
        # Passwords and OTPs must never appear in the response
        for forbidden in ["password", "otp", "biometric", "fingerprint"]:
            assert forbidden not in raw.lower(), (
                f"Sensitive field '{forbidden}' found in /recent-bookings response"
            )

    def test_recent_bookings_offset_pagination(self, client, admin_token):
        resp_p1 = client.get(
            "/api/admin/recent-bookings?limit=3&offset=0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        resp_p2 = client.get(
            "/api/admin/recent-bookings?limit=3&offset=3",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp_p1.status_code == 200
        assert resp_p2.status_code == 200
        ids_p1 = [b["allocation_id"] for b in resp_p1.get_json()["bookings"]]
        ids_p2 = [b["allocation_id"] for b in resp_p2.get_json()["bookings"]]
        # Both pages must return records; no record should appear on both pages
        # (tiebreaker by allocation_id ensures stable ordering even with equal timestamps)
        assert len(ids_p1) > 0, "Page 1 returned no records"
        assert len(ids_p2) > 0, "Page 2 returned no records"
        overlap = set(ids_p1) & set(ids_p2)
        assert not overlap, (
            f"Pagination overlap detected (tiebreaker ordering failure): "
            f"page1={ids_p1}, page2={ids_p2}, overlap={overlap}"
        )

    def test_recent_bookings_cap_at_100(self, client, admin_token):
        resp = client.get(
            "/api/admin/recent-bookings?limit=999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        assert resp.get_json()["page_info"]["limit"] == 100


# ---------------------------------------------------------------------------
# TASK 2: Login Page – CAPTCHA + OTP + solid white card
# ---------------------------------------------------------------------------

class TestLoginPageMarkup:
    """Static HTML structure tests for the updated login page."""

    @pytest.fixture(scope="class")
    def login_html(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "login.html"
        )
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_captcha_display_element_present(self, login_html):
        assert 'id="captchaDisplay"' in login_html, (
            "CAPTCHA display element not found in login.html"
        )

    def test_captcha_refresh_button_present(self, login_html):
        assert 'id="btnRefreshCaptcha"' in login_html, (
            "CAPTCHA refresh button not found in login.html"
        )

    def test_captcha_input_present(self, login_html):
        assert 'id="captchaInput"' in login_html, (
            "CAPTCHA input field not found in login.html"
        )

    def test_otp_input_removed(self, login_html):
        assert 'id="otpInput"' not in login_html, (
            "OTP input field '#otpInput' should be completely removed from login.html"
        )
        assert "ONE-TIME PASSWORD (OTP)" not in login_html, (
            "OTP label should be completely removed from login.html"
        )

    def test_heading_updated_to_aadhaar(self, login_html):
        assert "ENTER AADHAAR AUTHENTICATION ID" in login_html, (
            "Login heading not updated to 'ENTER AADHAAR AUTHENTICATION ID'"
        )

    def test_old_separator_removed(self, login_html):
        assert "--- OR ENTER SYNTHETIC EPIC NUMBER / VERIFICATION HASH ---" not in login_html, (
            "Old separator text still present in login.html"
        )

    def test_old_epic_input_removed(self, login_html):
        assert 'id="loginEpicInput"' not in login_html, (
            "Old loginEpicInput element still present in login.html"
        )

    def test_quick_select_dropdown_completely_removed(self, login_html):
        assert 'id="loginVoterSelect"' not in login_html, (
            "Quick-Select dropdown '#loginVoterSelect' still present in login.html"
        )
        assert "Quick-Select Demo Voter" not in login_html, (
            "References to 'Quick-Select Demo Voter' still present in login.html"
        )

    def test_aadhaar_input_present(self, login_html):
        assert 'id="aadhaarInput"' in login_html, (
            "Aadhaar input '#aadhaarInput' not found in login.html"
        )
        assert 'placeholder="XXXX-XXXX-XXXX"' in login_html, (
            "Aadhaar input missing placeholder 'XXXX-XXXX-XXXX'"
        )
        assert 'maxlength="14"' in login_html, (
            "Aadhaar input missing maxlength='14'"
        )
        assert 'inputmode="numeric"' in login_html, (
            "Aadhaar input missing inputmode='numeric'"
        )

    def test_aadhaar_input_auto_formatting_script_present(self, login_html):
        assert "aadhaarInput" in login_html, (
            "aadhaarInput handler not found in login.html script"
        )
        assert "XXXX-XXXX-XXXX" in login_html, (
            "XXXX-XXXX-XXXX formatting pattern not found in login.html script"
        )

    def test_proceed_button_still_present(self, login_html):
        assert 'id="btnProceedVoter"' in login_html, (
            "Proceed button not found in login.html"
        )

    def test_admin_panel_elements(self, login_html):
        assert 'id="loginAdminUser"' in login_html, (
            "Admin login username field removed from login.html"
        )
        assert 'id="loginAdminPass"' in login_html, (
            "Admin login password field removed from login.html"
        )
        assert 'id="btnAuthenticateAdmin"' in login_html, (
            "Admin authenticate button removed from login.html"
        )
        # Heading and demo role preset completely removed
        assert "ADMINISTRATOR JWT VERIFICATION" not in login_html.upper(), (
            "ADMINISTRATOR JWT VERIFICATION heading still present in login.html"
        )
        assert "DEMO ROLE PRESET" not in login_html.upper(), (
            "DEMO ROLE PRESET label still present in login.html"
        )
        assert 'id="loginAdminPreset"' not in login_html, (
            "Role preset dropdown '#loginAdminPreset' still present in login.html"
        )
        assert "State Election Logistics Officer" not in login_html, (
            "State Election Logistics Officer role option still present in login.html"
        )
        assert "ECI Central Observer" not in login_html, (
            "ECI Central Observer role option still present in login.html"
        )
        assert "Booth Returning Officer" not in login_html, (
            "Booth Returning Officer role option still present in login.html"
        )

    def test_admin_login_form_order(self, login_html):
        admin_panel_start = login_html.find('id="adminLoginPanel"')
        assert admin_panel_start != -1
        pos_user = login_html.find('ADMIN USERNAME', admin_panel_start)
        pos_pass = login_html.find('ADMIN PASSWORD', admin_panel_start)
        pos_captcha = login_html.find('CAPTCHA VERIFICATION', admin_panel_start)
        pos_btn = login_html.find('id="btnAuthenticateAdmin"', admin_panel_start)

        assert pos_user != -1, "ADMIN USERNAME label not found in adminLoginPanel"
        assert pos_pass != -1, "ADMIN PASSWORD label not found in adminLoginPanel"
        assert pos_captcha != -1, "CAPTCHA VERIFICATION label not found in adminLoginPanel"
        assert pos_btn != -1, "btnAuthenticateAdmin not found in adminLoginPanel"
        assert pos_user < pos_pass < pos_captcha < pos_btn, (
            "Admin login form elements not in order: USERNAME -> PASSWORD -> CAPTCHA -> BUTTON"
        )

    def test_admin_captcha_elements_present(self, login_html):
        assert 'id="adminCaptchaDisplay"' in login_html
        assert 'id="btnRefreshAdminCaptcha"' in login_html
        assert 'id="adminCaptchaInput"' in login_html

    def test_captcha_refresh_js_present(self, login_html):
        assert "refreshCaptcha" in login_html, (
            "refreshCaptcha function not found in login.html script"
        )

    def test_otp_validation_js_removed(self, login_html):
        assert "otpInput" not in login_html, (
            "otpInput reference should be removed from login.html script"
        )

    def test_server_side_captcha_endpoints_integrated(self, login_html):
        assert "/api/auth/captcha/generate" in login_html, (
            "login.html should call /api/auth/captcha/generate"
        )
        assert "/api/auth/captcha/validate" in login_html, (
            "login.html should call /api/auth/captcha/validate"
        )


class TestServerSideCaptchaEndpoints:
    """Tests for GET /api/auth/captcha/generate and POST /api/auth/captcha/validate."""

    @pytest.fixture(scope="class")
    def app(self):
        from backend.app import create_app
        application = create_app()
        application.config["TESTING"] = True
        return application

    @pytest.fixture(scope="class")
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_generate_captcha_returns_200_and_code(self, client):
        resp = client.get("/api/auth/captcha/generate")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("success") is True
        captcha = data.get("captcha")
        assert captcha is not None
        assert len(captcha) == 6
        assert captcha.isalnum()

    def test_validate_captcha_correct_answer_case_insensitive(self, client):
        resp = client.get("/api/auth/captcha/generate")
        data = resp.get_json()
        code = data["captcha"]

        # Validate with uppercase/lowercase variation
        val_resp = client.post("/api/auth/captcha/validate", json={"answer": code.upper()})
        assert val_resp.status_code == 200
        assert val_resp.get_json().get("valid") is True

    def test_validate_captcha_incorrect_answer_rejected(self, client):
        client.get("/api/auth/captcha/generate")
        val_resp = client.post("/api/auth/captcha/validate", json={"answer": "WRONG!"})
        assert val_resp.status_code == 400
        assert val_resp.get_json().get("valid") is False

    def test_validate_captcha_invalidates_challenge_after_use(self, client):
        resp = client.get("/api/auth/captcha/generate")
        code = resp.get_json()["captcha"]

        # First attempt succeeds
        val1 = client.post("/api/auth/captcha/validate", json={"answer": code})
        assert val1.status_code == 200

        # Replay attempt fails because challenge was invalidated
        val2 = client.post("/api/auth/captcha/validate", json={"answer": code})
        assert val2.status_code == 400

    def test_admin_scope_captcha_generate_and_validate(self, client):
        resp = client.get("/api/auth/captcha/generate?scope=admin")
        assert resp.status_code == 200
        code = resp.get_json()["captcha"]
        assert len(code) == 6

        # Validating with wrong answer fails
        val_bad = client.post("/api/auth/captcha/validate", json={"answer": "INCORRECT", "scope": "admin"})
        assert val_bad.status_code == 400

        # Refresh generates new code
        resp2 = client.get("/api/auth/captcha/generate?scope=admin")
        code2 = resp2.get_json()["captcha"]

        # Validating with correct answer succeeds
        val_good = client.post("/api/auth/captcha/validate", json={"answer": code2, "scope": "admin"})
        assert val_good.status_code == 200


class TestAadhaarAuthenticationEndpoint:
    """Tests for POST /api/auth/login with aadhaar_id."""

    @pytest.fixture(scope="class")
    def app(self):
        from backend.app import create_app
        application = create_app()
        application.config["TESTING"] = True
        return application

    @pytest.fixture(scope="class")
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_aadhaar_login_formatted_12_digits_success(self, client):
        resp = client.post("/api/auth/login", json={"aadhaar_id": "1234-5678-0001"})
        assert resp.status_code == 200, f"Expected 200, got: {resp.get_data(as_text=True)}"
        data = resp.get_json()
        assert data.get("success") is True
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["role"] == "VOTER"

    def test_aadhaar_login_raw_12_digits_success(self, client):
        resp = client.post("/api/auth/login", json={"aadhaar_id": "999988880002"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("success") is True
        assert data["user"]["demo_epic_no"] == "DEM-UK-2026-0002"

    def test_aadhaar_login_invalid_length_returns_400(self, client):
        resp = client.post("/api/auth/login", json={"aadhaar_id": "1234-5678"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data.get("error") == "BAD_REQUEST"

    def test_aadhaar_login_alphabetic_characters_rejected(self, client):
        resp = client.post("/api/auth/login", json={"aadhaar_id": "1234-ABCD-5678"})
        assert resp.status_code == 400


class TestLoginPageCSS:
    """CSS tests: glassmorphism removed, solid white card in place."""

    @pytest.fixture(scope="class")
    def styles_css(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "css", "styles.css"
        )
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_glassmorphism_backdrop_filter_removed(self, styles_css):
        # The @supports glassmorphism block must no longer exist
        assert "@supports (backdrop-filter" not in styles_css, (
            "Glassmorphism @supports block still present in styles.css"
        )

    def test_auth_card_has_solid_white_background(self, styles_css):
        assert "background: #ffffff" in styles_css, (
            "Solid white background (#ffffff) not found in authCard styles"
        )

    def test_auth_card_no_rgba_semi_transparent_background(self, styles_css):
        # rgba(255,255,255,0.18) and rgba(255,255,255,0.88) should be gone
        assert "rgba(255, 255, 255, 0.18)" not in styles_css, (
            "Semi-transparent glassmorphism background still in styles.css"
        )
        assert "rgba(255, 255, 255, 0.88)" not in styles_css, (
            "Fallback semi-transparent background still in styles.css"
        )

    def test_booking_row_animation_added(self, styles_css):
        assert "booking-row-new" in styles_css, (
            "booking-row-new animation class missing from styles.css"
        )
        assert "bookingRowIn" in styles_css, (
            "bookingRowIn keyframe missing from styles.css"
        )

    def test_auth_card_apple_squircle_corners(self, styles_css):
        assert "corner-shape: squircle" in styles_css, (
            "corner-shape: squircle property missing from styles.css"
        )
        assert "border-radius: 26px" in styles_css, (
            "border-radius: 26px fallback missing from styles.css"
        )


class TestAdminRecentBookingsFrontendIntegration:
    """Tests ensuring the admin dashboard properly integrates Recently Booked Voters."""

    @pytest.fixture(scope="class")
    def admin_html(self):
        path = os.path.join(os.path.dirname(__file__), "..", "frontend", "admin.html")
        with open(path, encoding="utf-8") as f:
            return f.read()

    @pytest.fixture(scope="class")
    def admin_js(self):
        path = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "admin_dashboard.js")
        with open(path, encoding="utf-8") as f:
            return f.read()

    @pytest.fixture(scope="class")
    def api_client_js(self):
        path = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "api_client.js")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_admin_table_headers_present(self, admin_html):
        for header in [
            "Ref / PNR", "Voter Name", "Category &amp; Priority",
            "Polling Station", "Booth", "Election Event",
            "Date &amp; Slot", "Status", "Booked At"
        ]:
            assert header in admin_html, f"Table header '{header}' missing from admin.html"

    def test_api_client_has_get_recent_bookings(self, api_client_js):
        assert "getRecentBookings" in api_client_js, (
            "getRecentBookings method missing from api_client.js"
        )
        assert "/api/admin/recent-bookings" in api_client_js

    def test_admin_dashboard_uses_api_client_method(self, admin_js):
        assert "window.apiClient.getRecentBookings" in admin_js, (
            "admin_dashboard.js must use window.apiClient.getRecentBookings"
        )

    def test_admin_dashboard_auto_refresh_configured(self, admin_js):
        assert "30000" in admin_js, (
            "30-second auto-refresh interval missing from admin_dashboard.js"
        )
