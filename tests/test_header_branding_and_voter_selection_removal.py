"""
Tests for:
  1. Removal of red-marked voter selection section from index.html (voter portal).
  2. Simplification of header branding to 'SMART AI POLL BOOTH ALLOCATION SYSTEM' across all pages.
"""

import os
import pytest

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))


def get_html(filename: str) -> str:
    path = os.path.join(FRONTEND_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestHeaderBrandingSimplification:
    """Verify header branding is simplified to 'SMART AI POLL BOOTH ALLOCATION SYSTEM'."""

    @pytest.mark.parametrize("filename", ["index.html", "login.html", "admin.html"])
    def test_single_title_in_header(self, filename):
        html = get_html(filename)
        assert "SMART AI POLL BOOTH ALLOCATION SYSTEM" in html, (
            f"Title 'SMART AI POLL BOOTH ALLOCATION SYSTEM' not found in {filename}"
        )

    @pytest.mark.parametrize("filename", ["index.html", "login.html", "admin.html"])
    def test_circular_logo_preserved(self, filename):
        html = get_html(filename)
        assert "/assets/vote_logo.png" in html, f"Logo image not found in {filename}"

    @pytest.mark.parametrize("filename", ["index.html", "login.html", "admin.html"])
    def test_header_subtitles_removed(self, filename):
        html = get_html(filename)
        header_start = html.find('<header class="main-header">')
        header_end = html.find('</header>', header_start)
        header_content = html[header_start:header_end]

        assert "One Nation One Election · Polling Logistics" not in header_content, (
            f"Subtitle 'One Nation One Election · Polling Logistics' still in header of {filename}"
        )
        assert "Smart Polling & Time-Slot Platform" not in header_content, (
            f"Subtitle 'Smart Polling & Time-Slot Platform' still in header of {filename}"
        )
        assert "IRCTC Authentication Gateway · Central" not in header_content, (
            f"Subtitle 'IRCTC Authentication Gateway' still in header of {filename}"
        )
        assert "Admin Logistics & Telemetry Console" not in header_content, (
            f"Subtitle 'Admin Logistics & Telemetry Console' still in header of {filename}"
        )

    @pytest.mark.parametrize("filename", ["index.html", "login.html", "admin.html"])
    def test_top_utility_and_advisory_preserved(self, filename):
        html = get_html(filename)
        assert "top-utility-bar" in html, f"Top utility bar missing in {filename}"
        assert "advisory-ticker" in html, f"Advisory banner missing in {filename}"


class TestVoterSelectionSectionRemoval:
    """Verify removal of red-marked voter selection elements in voter portal (index.html)."""

    @pytest.fixture(scope="class")
    def voter_html(self):
        return get_html("index.html")

    def test_quick_select_panel_removed(self, voter_html):
        assert 'id="quickSelectPanel"' not in voter_html, (
            "#quickSelectPanel must be completely removed from index.html"
        )

    def test_seeded_voter_dropdown_removed(self, voter_html):
        assert 'id="seededVoterSelect"' not in voter_html, (
            "#seededVoterSelect must be completely removed from index.html"
        )
        assert "Select Seeded Demo Voter" not in voter_html, (
            "'Select Seeded Demo Voter' heading must be removed from index.html"
        )

    def test_epic_direct_separator_removed(self, voter_html):
        assert "--- OR ENTER EPIC DIRECTLY ---" not in voter_html, (
            "'--- OR ENTER EPIC DIRECTLY ---' separator must be removed from index.html"
        )

    def test_manual_epic_input_and_fetch_button_removed(self, voter_html):
        assert 'id="manualEpicInput"' not in voter_html, (
            "#manualEpicInput must be removed from index.html"
        )
        assert 'id="btnLookupEpic"' not in voter_html, (
            "#btnLookupEpic (Fetch button) must be removed from index.html"
        )
        assert "Synthetic EPIC Card Number" not in voter_html, (
            "'Synthetic EPIC Card Number' label must be removed from index.html"
        )

    def test_voter_profile_card_preserved(self, voter_html):
        assert 'id="voterProfileCard"' in voter_html, (
            "#voterProfileCard must be preserved in index.html"
        )
        assert 'id="profVoterName"' in voter_html
        assert 'id="profVoterEpic"' in voter_html
        assert 'id="profCategoryBadge"' in voter_html
        assert 'id="profBoothName"' in voter_html
        assert 'id="profConstituency"' in voter_html
        assert 'id="profVerifStatus"' in voter_html
        assert 'id="profActiveBookingAlert"' in voter_html
        assert 'id="btnProceedToStep2"' in voter_html, (
            "#btnProceedToStep2 (Proceed to ECI Verification) must be preserved"
        )

    def test_no_empty_gap_or_broken_structure(self, voter_html):
        assert "quickSelectPanel" not in voter_html
        # No red annotation artifacts
        assert "red-marked" not in voter_html
        assert "annotation" not in voter_html
