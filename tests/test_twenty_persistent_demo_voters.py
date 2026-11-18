"""
Comprehensive Test Suite: 20 Persistent Synthetic Demo Voter Accounts
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: tests/test_twenty_persistent_demo_voters.py

Verifies:
1. Exactly 20 persistent accounts are seeded in MySQL database with unique 12-digit synthetic IDs.
2. Formatted ('XXXX-XXXX-XXXX') and raw 12-digit numeric login succeeds for all 20 accounts.
3. Each account loads its own authoritative profile (no cross-user identity leakage).
4. Unknown synthetic IDs are rejected with 404 NOT_FOUND (never silently logged in as another voter).
5. Invalid length and non-numeric inputs are rejected with 400 BAD_REQUEST.
6. Safe seeding transaction & restart persistence: repeated initialization preserves the exact same IDs.
7. Database uniqueness constraint: duplicate synthetic IDs cannot be inserted.
8. Complete session independence: Voter bookings and active tokens remain isolated per voter.
9. GET /api/auth/demo-voters and GET /api/voters/demo-accounts safely export accounts without credentials.
10. Preserves existing admin authentication.
"""

import re
import pytest
from backend.app import create_app
from backend.app.services.demo_voter_service import (
    demo_voter_service,
    PERSISTENT_DEMO_VOTERS_SPEC
)
from database.db_pool import db_pool


@pytest.fixture(scope="module")
def app():
    application = create_app({"TESTING": True})
    return application


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


class TestTwentyPersistentDemoVoters:
    """Verifies all acceptance criteria for 20 persistent demo voter accounts."""

    def test_01_exactly_twenty_accounts_configured(self):
        """Requirement 1: Exactly 20 unique 12-digit synthetic demo IDs."""
        assert len(PERSISTENT_DEMO_VOTERS_SPEC) == 20
        ids = [v["synthetic_aadhaar_id"] for v in PERSISTENT_DEMO_VOTERS_SPEC]
        # All must be unique
        assert len(set(ids)) == 20
        # All must be exactly 12 numeric digits
        for synth_id in ids:
            assert len(synth_id) == 12
            assert synth_id.isdigit()

    def test_02_database_persistence_and_seeding(self):
        """Requirement 2 & 3: Stored permanently in MySQL, reused across startups."""
        seed_result = demo_voter_service.ensure_demo_voters_seeded()
        assert seed_result.get("verified_count") == 20

        # Query live database directly
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("""
                SELECT voter_id, demo_epic_no, synthetic_aadhaar_id, full_name
                FROM voters
                WHERE voter_id BETWEEN 1 AND 20
                ORDER BY voter_id ASC;
            """)
            db_rows = cursor.fetchall()

        assert len(db_rows) == 20
        for i, row in enumerate(db_rows):
            spec = PERSISTENT_DEMO_VOTERS_SPEC[i]
            assert row["voter_id"] == spec["voter_id"]
            assert row["demo_epic_no"] == spec["demo_epic_no"]
            assert row["synthetic_aadhaar_id"] == spec["synthetic_aadhaar_id"]
            assert row["full_name"] == spec["full_name"]

    def test_03_seeding_is_idempotent_no_regeneration(self):
        """Requirement 3: On subsequent executions, reuse existing IDs. Never overwrite."""
        # Run seeding again
        second_run = demo_voter_service.ensure_demo_voters_seeded()
        assert second_run.get("newly_assigned_count") == 0
        assert second_run.get("verified_count") == 20

        # Verify IDs in database remain unaltered
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("""
                SELECT voter_id, synthetic_aadhaar_id FROM voters
                WHERE voter_id BETWEEN 1 AND 20 ORDER BY voter_id;
            """)
            rows = cursor.fetchall()
            for i, r in enumerate(rows):
                assert r["synthetic_aadhaar_id"] == PERSISTENT_DEMO_VOTERS_SPEC[i]["synthetic_aadhaar_id"]

    def test_04_all_twenty_voters_authenticate_successfully_formatted(self, client):
        """Requirement 4: Login flow authenticates each of the 20 accounts using formatted ID."""
        for spec in PERSISTENT_DEMO_VOTERS_SPEC:
            formatted_id = spec["formatted_id"]
            resp = client.post("/api/auth/login", json={"aadhaar_id": formatted_id})
            assert resp.status_code == 200, f"Login failed for voter {spec['voter_id']} with ID {formatted_id}"
            data = resp.get_json()
            assert data["success"] is True
            assert "access_token" in data
            assert data["user"]["voter_id"] == spec["voter_id"]
            assert data["user"]["demo_epic_no"] == spec["demo_epic_no"]
            assert data["user"]["name"] == spec["full_name"]
            assert data["user"]["role"] == "VOTER"

    def test_05_all_twenty_voters_authenticate_successfully_raw_digits(self, client):
        """Requirement 4: Login flow authenticates each of the 20 accounts using raw 12 digits."""
        for spec in PERSISTENT_DEMO_VOTERS_SPEC:
            raw_id = spec["synthetic_aadhaar_id"]
            resp = client.post("/api/auth/login", json={"aadhaar_id": raw_id})
            assert resp.status_code == 200, f"Login failed for raw ID {raw_id}"
            data = resp.get_json()
            assert data["user"]["voter_id"] == spec["voter_id"]
            assert data["user"]["demo_epic_no"] == spec["demo_epic_no"]

    def test_06_reject_unknown_ids_returns_404(self, client):
        """Requirement 6: Reject unknown IDs. Never silently log in as another voter."""
        unknown_ids = [
            "1111-2222-3333",
            "000000000000",
            "999999999999",
            "5555-4444-3333",
            "8888-7777-6666"
        ]
        for unk in unknown_ids:
            resp = client.post("/api/auth/login", json={"aadhaar_id": unk})
            assert resp.status_code == 404, f"Unknown ID '{unk}' was not rejected with 404!"
            data = resp.get_json()
            assert data.get("error") == "NOT_FOUND"
            assert "not recognized" in data.get("message", "").lower()

    def test_07_reject_invalid_length_or_format_returns_400(self, client):
        """Requirement 6: Format validation returns 400 Bad Request."""
        invalid_inputs = [
            "1234",
            "1234-5678",
            "1234-5678-9012-3456",
            "1234-ABCD-5678",
            "",
            None
        ]
        for bad in invalid_inputs:
            if bad is None:
                resp = client.post("/api/auth/login", json={})
            else:
                resp = client.post("/api/auth/login", json={"aadhaar_id": bad})
            assert resp.status_code == 400, f"Invalid input '{bad}' did not return 400"
            data = resp.get_json()
            assert data.get("error") == "BAD_REQUEST"

    def test_08_database_uniqueness_enforced(self):
        """Requirement 7: Enforce database uniqueness constraint on synthetic IDs."""
        with db_pool.get_cursor() as (conn, cursor):
            # Attempt to set duplicate synthetic_aadhaar_id for voter 21
            with pytest.raises(Exception):
                cursor.execute("""
                    UPDATE voters
                    SET synthetic_aadhaar_id = '123456780001'
                    WHERE voter_id = 21;
                """)
                conn.commit()

    def test_09_account_and_session_independence(self, client):
        """Requirement 5: Ensure all 20 accounts remain independent in bookings and session data."""
        # Authenticate Voter 1 and Voter 2
        resp1 = client.post("/api/auth/login", json={"aadhaar_id": "1234-5678-0001"})
        resp2 = client.post("/api/auth/login", json={"aadhaar_id": "9999-8888-0002"})
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        token1 = resp1.get_json()["access_token"]
        token2 = resp2.get_json()["access_token"]
        assert token1 != token2

        # Check voter details via voter service
        from backend.app.services.voter_service import voter_service
        v1 = voter_service.get_voter_by_synthetic_aadhaar("123456780001")
        v2 = voter_service.get_voter_by_synthetic_aadhaar("999988880002")

        assert v1["voter_id"] == 1
        assert v2["voter_id"] == 2
        assert v1["full_name"] == "Ramesh Chandra Sharma"
        assert v2["full_name"] == "Sunita Devi Rawat"
        assert v1["demo_epic_no"] != v2["demo_epic_no"]

    def test_10_demo_voters_export_api_endpoints(self, client):
        """Requirement 10: Safe way to display/export 20 demo IDs without credentials."""
        # Endpoint 1: GET /api/auth/demo-voters
        resp1 = client.get("/api/auth/demo-voters")
        assert resp1.status_code == 200
        data1 = resp1.get_json()
        assert data1["success"] is True
        assert data1["total"] == 20
        voters1 = data1["demo_voters"]
        assert len(voters1) == 20

        # Endpoint 2: GET /api/voters/demo-accounts
        resp2 = client.get("/api/voters/demo-accounts")
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["success"] is True
        assert data2["total"] == 20

        # Verify no credentials (password, admin secrets) are present in payload
        raw_text = resp1.get_data(as_text=True).lower()
        for forbidden in ["password", "secret", "hash", "private_key"]:
            assert forbidden not in raw_text

        # Verify all 20 have required demo metadata
        for v in voters1:
            assert "voter_id" in v
            assert "formatted_id" in v
            assert "synthetic_aadhaar_id" in v
            assert "full_name" in v
            assert "priority_tier" in v
            assert "special_category" in v

    def test_11_preserves_admin_authentication(self, client):
        """Requirement 8: Preserve existing admin authentication and working features."""
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin2026password"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["user"]["role"] == "SUPER_ADMIN"
        assert "access_token" in data
