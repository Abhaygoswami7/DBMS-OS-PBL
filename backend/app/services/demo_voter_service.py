"""
Persistent Demo Voter Management Service
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/services/demo_voter_service.py

Manages exactly 20 persistent, unique, synthetic 12-digit demo voter accounts
mapped to User 1 through User 20.

STRICT PRIVACY & GUARDRAILS COMPLIANCE:
1. 100% synthetic mock identifiers. Zero real citizen data, zero real UIDAI Aadhaar.
2. Persistent in MySQL database. Never regenerated, duplicated, or overwritten on restarts.
3. Safe transactions with database uniqueness constraints.
"""

import json
import logging
import os
import re
from typing import Dict, Any, List, Optional
from database.db_pool import db_pool

logger = logging.getLogger("demo_voter_service")

# Authoritative specification of 20 persistent demo voters (Users 1 to 20)
# Exactly 20 unique 12-digit synthetic demo identifiers
PERSISTENT_DEMO_VOTERS_SPEC: List[Dict[str, Any]] = [
    {"voter_id": 1,  "demo_epic_no": "DEM-UK-2026-0001", "synthetic_aadhaar_id": "123456780001", "formatted_id": "1234-5678-0001", "full_name": "Ramesh Chandra Sharma", "category": "SENIOR_CITIZEN",         "priority_level": 3, "priority_tier": "P3"},
    {"voter_id": 2,  "demo_epic_no": "DEM-UK-2026-0002", "synthetic_aadhaar_id": "999988880002", "formatted_id": "9999-8888-0002", "full_name": "Sunita Devi Rawat",     "category": "SENIOR_CITIZEN",         "priority_level": 3, "priority_tier": "P3"},
    {"voter_id": 3,  "demo_epic_no": "DEM-UK-2026-0003", "synthetic_aadhaar_id": "847291035621", "formatted_id": "8472-9103-5621", "full_name": "Arvind Singh Negi",     "category": "PERSON_WITH_DISABILITY", "priority_level": 2, "priority_tier": "P2"},
    {"voter_id": 4,  "demo_epic_no": "DEM-UK-2026-0004", "synthetic_aadhaar_id": "619284730192", "formatted_id": "6192-8473-0192", "full_name": "Deepa Joshi",           "category": "PREGNANT_WOMEN",         "priority_level": 1, "priority_tier": "P1"},
    {"voter_id": 5,  "demo_epic_no": "DEM-UK-2026-0005", "synthetic_aadhaar_id": "384910295738", "formatted_id": "3849-1029-5738", "full_name": "Manmohan Singh Bisht",  "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"},
    {"voter_id": 6,  "demo_epic_no": "DEM-UK-2026-0006", "synthetic_aadhaar_id": "729401826491", "formatted_id": "7294-0182-6491", "full_name": "Pooja Bhatt",           "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"},
    {"voter_id": 7,  "demo_epic_no": "DEM-UK-2026-0007", "synthetic_aadhaar_id": "481920384756", "formatted_id": "4819-2038-4756", "full_name": "Vikram Pant",           "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"},
    {"voter_id": 8,  "demo_epic_no": "DEM-UK-2026-0008", "synthetic_aadhaar_id": "938471029482", "formatted_id": "9384-7102-9482", "full_name": "Neelam Chauhan",        "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"},
    {"voter_id": 9,  "demo_epic_no": "DEM-UK-2026-0009", "synthetic_aadhaar_id": "510293847561", "formatted_id": "5102-9384-7561", "full_name": "Bhagwati Prasad Uniyal","category": "SENIOR_CITIZEN",         "priority_level": 3, "priority_tier": "P3"},
    {"voter_id": 10, "demo_epic_no": "DEM-UK-2026-0010", "synthetic_aadhaar_id": "274819203948", "formatted_id": "2748-1920-3948", "full_name": "Kamla Devi Khanduri",   "category": "SENIOR_CITIZEN",         "priority_level": 3, "priority_tier": "P3"},
    {"voter_id": 11, "demo_epic_no": "DEM-UK-2026-0011", "synthetic_aadhaar_id": "639201948572", "formatted_id": "6392-0194-8572", "full_name": "Suresh Kumar Thapa",    "category": "PERSON_WITH_DISABILITY", "priority_level": 2, "priority_tier": "P2"},
    {"voter_id": 12, "demo_epic_no": "DEM-UK-2026-0012", "synthetic_aadhaar_id": "184920384729", "formatted_id": "1849-2038-4729", "full_name": "Anjali Gurung",         "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"},
    {"voter_id": 13, "demo_epic_no": "DEM-UK-2026-0013", "synthetic_aadhaar_id": "749201837492", "formatted_id": "7492-0183-7492", "full_name": "Gaurav Semwal",         "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"},
    {"voter_id": 14, "demo_epic_no": "DEM-UK-2026-0014", "synthetic_aadhaar_id": "395810294827", "formatted_id": "3958-1029-4827", "full_name": "Meenakshi Thapliyal",   "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"},
    {"voter_id": 15, "demo_epic_no": "DEM-UK-2026-0015", "synthetic_aadhaar_id": "827491029471", "formatted_id": "8274-9102-9471", "full_name": "Rohit Gairola",         "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"},
    {"voter_id": 16, "demo_epic_no": "DEM-UK-2026-0016", "synthetic_aadhaar_id": "491029485720", "formatted_id": "4910-2948-5720", "full_name": "Kavita Nautiyal",       "category": "PREGNANT_WOMEN",         "priority_level": 1, "priority_tier": "P1"},
    {"voter_id": 17, "demo_epic_no": "DEM-UK-2026-0017", "synthetic_aadhaar_id": "602938471928", "formatted_id": "6029-3847-1928", "full_name": "Dharam Singh Rana",     "category": "SENIOR_CITIZEN",         "priority_level": 3, "priority_tier": "P3"},
    {"voter_id": 18, "demo_epic_no": "DEM-UK-2026-0018", "synthetic_aadhaar_id": "284719203849", "formatted_id": "2847-1920-3849", "full_name": "Shanti Devi Panwar",    "category": "SENIOR_CITIZEN",         "priority_level": 3, "priority_tier": "P3"},
    {"voter_id": 19, "demo_epic_no": "DEM-UK-2026-0019", "synthetic_aadhaar_id": "918273645019", "formatted_id": "9182-7364-5019", "full_name": "Naveen Chandra Tiwari", "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"},
    {"voter_id": 20, "demo_epic_no": "DEM-UK-2026-0020", "synthetic_aadhaar_id": "573829104928", "formatted_id": "5738-2910-4928", "full_name": "Rachna Dobhal",         "category": "GENERAL",                 "priority_level": 4, "priority_tier": "P4"}
]

# Quick lookup cache by clean 12-digit string
_SPEC_BY_AADHAAR: Dict[str, Dict[str, Any]] = {
    v["synthetic_aadhaar_id"]: v for v in PERSISTENT_DEMO_VOTERS_SPEC
}
_SPEC_BY_VOTER_ID: Dict[int, Dict[str, Any]] = {
    v["voter_id"]: v for v in PERSISTENT_DEMO_VOTERS_SPEC
}


class DemoVoterService:
    """Service ensuring persistent, idempotent storage and retrieval of the 20 demo accounts."""

    @staticmethod
    def format_aadhaar_id(raw_digits: str) -> str:
        """Formats 12 numeric digits into XXXX-XXXX-XXXX display format."""
        clean = re.sub(r"\D", "", str(raw_digits or ""))
        if len(clean) == 12:
            return f"{clean[:4]}-{clean[4:8]}-{clean[8:]}"
        return raw_digits

    @staticmethod
    def clean_aadhaar_id(value: str) -> str:
        """Extracts purely numeric digits from input."""
        return re.sub(r"\D", "", str(value or ""))

    def ensure_demo_voters_seeded(self) -> Dict[str, Any]:
        """
        Idempotent database seeding and verification.
        1. Ensures `synthetic_aadhaar_id` column and UNIQUE constraint exist on `voters`.
        2. Populates Users 1 to 20 with their persistent 12-digit synthetic IDs.
        3. Never regenerates, duplicates, or overwrites existing IDs.
        4. Runs within an ACID transaction.
        """
        result = {
            "column_ensured": False,
            "existing_assigned_count": 0,
            "newly_assigned_count": 0,
            "verified_count": 0
        }

        try:
            with db_pool.get_cursor() as (conn, cursor):
                # 1. Check if synthetic_aadhaar_id column exists
                cursor.execute("""
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'voters'
                      AND COLUMN_NAME = 'synthetic_aadhaar_id';
                """)
                col = cursor.fetchone()
                if not col:
                    cursor.execute("""
                        ALTER TABLE voters
                        ADD COLUMN synthetic_aadhaar_id VARCHAR(16) NULL UNIQUE AFTER demo_epic_no;
                    """)
                    conn.commit()
                    result["column_ensured"] = True
                    logger.info("Added synthetic_aadhaar_id column to voters table.")
                else:
                    result["column_ensured"] = True

                # 2. Check existing count of populated demo voters (1 to 20)
                cursor.execute("""
                    SELECT voter_id, synthetic_aadhaar_id
                    FROM voters
                    WHERE voter_id BETWEEN 1 AND 20 AND synthetic_aadhaar_id IS NOT NULL;
                """)
                existing_rows = cursor.fetchall()
                existing_map = {r["voter_id"]: r["synthetic_aadhaar_id"] for r in existing_rows}
                result["existing_assigned_count"] = len(existing_map)

                # 3. If all 20 are already populated, verify consistency and return
                if len(existing_map) == 20:
                    result["verified_count"] = 20
                    return result

                # 4. Safe transaction: assign persistent IDs to unpopulated voter records
                newly_assigned = 0
                for spec in PERSISTENT_DEMO_VOTERS_SPEC:
                    vid = spec["voter_id"]
                    synth_id = spec["synthetic_aadhaar_id"]

                    if vid not in existing_map or not existing_map[vid]:
                        cursor.execute("""
                            UPDATE voters
                            SET synthetic_aadhaar_id = %s
                            WHERE voter_id = %s;
                        """, (synth_id, vid))
                        newly_assigned += 1

                conn.commit()
                result["newly_assigned_count"] = newly_assigned

                # 5. Final count check
                cursor.execute("""
                    SELECT COUNT(*) as cnt
                    FROM voters
                    WHERE voter_id BETWEEN 1 AND 20 AND synthetic_aadhaar_id IS NOT NULL;
                """)
                final_cnt = cursor.fetchone()["cnt"]
                result["verified_count"] = final_cnt
                logger.info(
                    "Demo voter seeding complete: %d existing, %d newly assigned, %d total verified.",
                    result["existing_assigned_count"],
                    result["newly_assigned_count"],
                    result["verified_count"]
                )

        except Exception as e:
            logger.error("Failed ensuring persistent demo voters: %s", e)
            result["error"] = str(e)

        return result

    def get_all_demo_voters(self) -> List[Dict[str, Any]]:
        """
        Retrieves all 20 persistent demo voter profiles with live database state.
        Excludes sensitive administrator credentials.
        """
        query = """
        SELECT
            v.voter_id,
            v.demo_epic_no,
            v.synthetic_aadhaar_id,
            v.full_name,
            v.special_category,
            v.priority_level,
            v.simulated_verification_status,
            v.assigned_booth_id,
            b.booth_number,
            b.booth_name,
            ps.station_name,
            pc.constituency_name AS parliamentary_constituency,
            ac.constituency_name AS assembly_constituency,
            (SELECT COUNT(*) FROM slot_allocations sa WHERE sa.voter_id = v.voter_id AND sa.status IN ('CONFIRMED', 'CHECKED_IN')) AS has_active_booking,
            (SELECT sa.booking_reference_token FROM slot_allocations sa WHERE sa.voter_id = v.voter_id AND sa.status IN ('CONFIRMED', 'CHECKED_IN') ORDER BY sa.allocation_id DESC LIMIT 1) AS active_token
        FROM voters v
        JOIN polling_booths b ON v.assigned_booth_id = b.booth_id
        JOIN polling_stations ps ON b.station_id = ps.station_id
        JOIN constituencies pc ON b.pc_id = pc.constituency_id
        JOIN constituencies ac ON b.ac_id = ac.constituency_id
        WHERE v.voter_id BETWEEN 1 AND 20
        ORDER BY v.voter_id ASC;
        """
        try:
            with db_pool.get_cursor() as (conn, cursor):
                cursor.execute(query)
                rows = cursor.fetchall()
                voters = []
                tier_map = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}
                for r in rows:
                    raw_id = r.get("synthetic_aadhaar_id") or ""
                    # Fallback to spec if DB record is not yet seeded
                    if not raw_id and r["voter_id"] in _SPEC_BY_VOTER_ID:
                        raw_id = _SPEC_BY_VOTER_ID[r["voter_id"]]["synthetic_aadhaar_id"]

                    formatted = self.format_aadhaar_id(raw_id)
                    masked = f"XXXX-XXXX-{raw_id[-4:]}" if len(raw_id) == 12 else "XXXX-XXXX-XXXX"

                    voters.append({
                        "voter_id": r["voter_id"],
                        "demo_epic_no": r["demo_epic_no"],
                        "synthetic_aadhaar_id": raw_id,
                        "formatted_id": formatted,
                        "masked_id": masked,
                        "full_name": r["full_name"],
                        "special_category": r["special_category"],
                        "priority_level": r["priority_level"],
                        "priority_tier": tier_map.get(r["priority_level"], "P4"),
                        "simulated_verification_status": r["simulated_verification_status"],
                        "assigned_booth_id": r["assigned_booth_id"],
                        "booth_number": r["booth_number"],
                        "booth_name": r["booth_name"],
                        "station_name": r["station_name"],
                        "parliamentary_constituency": r["parliamentary_constituency"],
                        "assembly_constituency": r["assembly_constituency"],
                        "has_active_booking": bool(r.get("has_active_booking", 0)),
                        "active_token": r.get("active_token")
                    })
                return voters
        except Exception as e:
            logger.error("Error retrieving demo voters from database: %s", e)
            # Safe offline fallback from specification
            return PERSISTENT_DEMO_VOTERS_SPEC

    def export_demo_voters_json(self, output_path: str) -> bool:
        """Exports the 20 demo accounts to a clean JSON file for testing."""
        try:
            data = self.get_all_demo_voters()
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({
                    "meta": {
                        "description": "VoteIT 20 Persistent Synthetic Demo Voter Accounts",
                        "total_accounts": len(data),
                        "notice": "SYNTHETIC DEMO IDENTIFIERS ONLY. Zero real citizen credentials."
                    },
                    "demo_voters": data
                }, f, indent=2)
            return True
        except Exception as e:
            logger.error("Failed exporting demo voters to %s: %s", output_path, e)
            return False


# Singleton instance
demo_voter_service = DemoVoterService()
