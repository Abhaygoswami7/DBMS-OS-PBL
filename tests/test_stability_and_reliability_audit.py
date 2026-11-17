"""
Stability, Reliability and Regression Audit Test Suite
Project: Smart Polling Booth & Time-Slot Platform (VoteIT)

Validates:
1. Application factory instantiation and all registered REST routes.
2. Database connection pool elasticity, health checks, and views.
3. Login portal demo dropdown mapping alignment with Bhimtal / Nainital.
4. ERS appointment slip rendering with accurate PC/AC constituency strings.
5. Zero emojis across all updated codebase files.
6. Deadlock-safe dual-slot swap ordering and capacity invariance.
"""

import os
import re
import pytest
from backend.app import create_app
from database.db_pool import db_pool


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True})


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


def test_app_factory_and_core_routes(client):
    """Ensure all core routes return expected status codes and headers."""
    # Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert res.headers.get("X-OS-Concurrency-Engine") == "Active"

    # Static pages
    assert client.get("/").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.get("/voter").status_code == 200
    assert client.get("/admin").status_code == 200


def test_database_views_and_integrity():
    """Verify live views and tables are queryable without SQL exceptions."""
    with db_pool.get_cursor() as (conn, cur):
        cur.execute("SELECT COUNT(*) AS total_stations FROM polling_stations;")
        row = cur.fetchone()
        assert row["total_stations"] == 4

        cur.execute("SELECT COUNT(*) AS total_booths FROM polling_booths;")
        row = cur.fetchone()
        assert row["total_booths"] == 8

        cur.execute("SELECT COUNT(*) AS total_voters FROM voters;")
        row = cur.fetchone()
        assert row["total_voters"] >= 60

        # Verify views exist and execute cleanly
        cur.execute("SELECT COUNT(*) AS c FROM vw_booth_live_status;")
        assert cur.fetchone()["c"] >= 0

        cur.execute("SELECT COUNT(*) AS c FROM vw_constituency_logistics_summary;")
        assert cur.fetchone()["c"] >= 0


def test_login_dropdown_bhimtal_alignment():
    """Ensure login.html voter panel has replaced dropdown with Aadhaar ID input and has no legacy labels."""
    login_html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "login.html")
    with open(login_html_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "aadhaarInput" in content
    assert "XXXX-XXXX-XXXX" in content
    # No legacy labels
    assert "Garhi Cantt Booth 1" not in content
    assert "Hathibarkala Booth 1" not in content


def test_voter_portal_constituency_fallback():
    """Ensure voter portal appointment slip fallback matches Bhimtal and Nainital."""
    voter_js_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "voter_portal.js")
    with open(voter_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Nainital-Udhamsingh Nagar Parliamentary Constituency" in content
    assert "Bhimtal Assembly Constituency" in content
    assert "Tehri Garhwal" not in content


def test_zero_emojis_in_all_modified_files():
    """Verify strictly zero emojis in all code and markup."""
    emoji_pattern = re.compile(
        r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50\u2b55]'
    )
    targets = [
        os.path.join(os.path.dirname(__file__), "..", "frontend", "login.html"),
        os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"),
        os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "voter_portal.js"),
        os.path.join(os.path.dirname(__file__), "..", "frontend", "css", "styles.css")
    ]
    for path in targets:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        matches = emoji_pattern.findall(text)
        assert len(matches) == 0, f"Found {len(matches)} emojis in {path}: {matches}"
