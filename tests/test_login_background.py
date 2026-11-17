"""
Test Suite for Login Page Full-Page Background Integration.
Validates:
1. Static image serving at /assets/login-background.jpg (Status 200, image/jpeg).
2. login.html structure, body.login-page class, and centered auth card.
3. styles.css rules for body.login-page (background-size, position, repeat, overlay, flex centering).
4. Voter login and Admin login endpoints functionality.
"""

import pytest
from backend.app import create_app
from pathlib import Path


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True})


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


def test_login_background_asset_serving(client):
    """Verify that /assets/login-background.jpg is served correctly with HTTP 200."""
    res = client.get("/assets/login-background.jpg")
    assert res.status_code == 200
    assert "image/jpeg" in res.content_type
    assert len(res.data) > 0


def test_login_html_contains_login_page_class(client):
    """Verify login.html applies the login-page class and proper structure."""
    res = client.get("/login")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    assert '<body class="login-page">' in html
    assert 'id="authCard"' in html
    assert 'main-content' in html
    assert '/assets/vote_logo.png' in html


def test_styles_css_contains_background_specifications(client):
    """Verify styles.css includes cover, center center, no-repeat, overlay, and centering."""
    res = client.get("/css/styles.css")
    assert res.status_code == 200
    css = res.get_data(as_text=True)

    assert "body.login-page" in css
    assert "/assets/login-background.jpg" in css
    assert "background-size: cover" in css
    assert "background-position: center center" in css
    assert "background-repeat: no-repeat" in css
    assert "linear-gradient" in css
    assert "display: flex" in css
    assert "align-items: center" in css
    assert "justify-content: center" in css

    # Solid card: glassmorphism was intentionally removed in favour of a clean white card.
    # Verify the solid white background is present instead.
    assert "background: #ffffff" in css


def test_login_authentication_endpoint_functionality(client):
    """Verify that voter lookup and admin login authentication endpoints function properly."""
    # Voter lookup
    res_voter = client.post("/api/voters/register", json={
        "demo_epic_no": "DEM-UK-2026-0001",
        "action": "lookup"
    })
    assert res_voter.status_code == 200
    voter_data = res_voter.get_json()
    assert voter_data.get("success") is True
    assert voter_data.get("voter", {}).get("demo_epic_no") == "DEM-UK-2026-0001"

    # Admin authentication
    res_admin = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "Admin@ONOE2026!"
    })
    assert res_admin.status_code == 200
    admin_data = res_admin.get_json()
    assert admin_data.get("success") is True
    assert "access_token" in admin_data
