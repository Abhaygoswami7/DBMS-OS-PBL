"""
VoteIT Test Suite: Simplified ECI Verification Display Verification
Verifies that cryptographic tokens/hashes are removed from the frontend UI,
replaced by a clean success banner with checkmark and 'Status: VERIFIED',
while backend token generation, anonymization, and database storage remain intact.
"""

import re
import pytest
from pathlib import Path
from backend.app import create_app


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True})


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture
def index_html():
    p = Path("frontend/index.html")
    assert p.exists()
    return p.read_text(encoding="utf-8")


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


def test_token_hash_removed_from_html(index_html):
    """Verify that verifResultToken and raw token display containers are removed from HTML."""
    assert "verifResultToken" not in index_html, "Lengthy token container verifResultToken must be removed"
    assert "No active token" not in index_html, "Stale token placeholder must be removed"


def test_clean_success_banner_in_html(index_html):
    """Verify clean success banner elements with checkmark and VERIFIED status."""
    assert 'id="verifSuccessNotice"' in index_html, "verifSuccessNotice container must exist"
    assert "Identity Verification Successful" in index_html, "Success message must be present"
    assert "VERIFIED" in index_html, "VERIFIED status indicator must be present"
    assert "&#10003;" in index_html or "✓" in index_html, "Checkmark must be present"


def test_voter_portal_does_not_display_token_in_dom(voter_portal_js):
    """Verify JS handles verifSuccessNotice without rendering raw token string in DOM."""
    assert "verifSuccessNotice" in voter_portal_js, "Must reference verifSuccessNotice"
    assert "verifResultToken.textContent" not in voter_portal_js, "Must not set token text in DOM"
    assert "verifSuccessNotice.style.display" in voter_portal_js, "Must toggle verifSuccessNotice display"


def test_styles_css_contains_clean_success_banner(styles_css):
    """Verify styling for .verif-success-banner with green theme."""
    assert ".verif-success-banner" in styles_css
    assert "var(--irctc-status-avl" in styles_css
    assert ".verif-title" in styles_css
    assert ".verif-check" in styles_css


def test_backend_verification_anonymized_token_retained(client):
    """Verify backend still generates anonymized token and updates database correctly."""
    res = client.post("/api/verification/mock", json={
        "voter_id": 1,
        "booth_id": 1,
        "consent_given": True,
        "verification_method": "SIMULATED_OTP",
        "mock_input": "987654321098"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "simulated_token" in data
    # Token must be 64-character SHA-256 hex string
    assert len(data["simulated_token"]) == 64
    assert data["status"] == "PASSED"


def test_strictly_zero_emojis_in_frontend(index_html, voter_portal_js, styles_css):
    """Ensure zero emojis across all frontend files."""
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)
    assert len(emoji_pattern.findall(index_html)) == 0
    assert len(emoji_pattern.findall(voter_portal_js)) == 0
    assert len(emoji_pattern.findall(styles_css)) == 0
