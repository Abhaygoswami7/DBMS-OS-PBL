"""
Voter Registry & Synthetic Profile Management Service
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Handles:
  1. Voter retrieval by synthetic identifier (DEM-UK-2026-XXXX) or voter_id.
  2. Verification and priority tier categorization (Senior Citizen, PwD, Expectant Mothers, General).
  3. Jurisdictional mapping to Booth, Station, Parliamentary (PC), and Assembly (AC) Constituencies.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from database.db_pool import db_pool
from backend.app.os_engine.memory_and_logger import os_file_logger

logger = logging.getLogger("voter_service")

class VoterService:
    """Service managing synthetic demo voter accounts and jurisdictional data."""
    
    # Strict synthetic identifier regex: DEM-UK-2026-XXXX
    SYNTHETIC_EPIC_PATTERN = re.compile(r"^DEM-UK-2026-\d{4}$")

    def get_voter_by_demo_epic(self, demo_epic_no: str) -> Optional[Dict[str, Any]]:
        """Retrieves synthetic voter details with full jurisdictional booth mapping."""
        clean_epic = demo_epic_no.strip().upper()
        if not self.SYNTHETIC_EPIC_PATTERN.match(clean_epic):
            logger.warning("Rejected non-synthetic identifier: %s", clean_epic)
            return None

        query = """
        SELECT
            v.voter_id,
            v.demo_epic_no,
            v.full_name,
            v.dob,
            v.gender,
            v.address_zone,
            v.pincode,
            v.special_category,
            v.priority_level,
            v.simulated_verification_status,
            v.assigned_booth_id,
            b.booth_number,
            b.booth_name,
            b.room_number,
            ps.station_id,
            ps.station_code,
            ps.station_name,
            ps.address AS station_address,
            ps.pincode AS station_pincode,
            ps.has_wheelchair_ramp,
            pc.constituency_code AS pc_code,
            pc.constituency_name AS parliamentary_constituency,
            ac.constituency_code AS ac_code,
            ac.constituency_name AS assembly_constituency
        FROM voters v
        JOIN polling_booths b ON v.assigned_booth_id = b.booth_id
        JOIN polling_stations ps ON b.station_id = ps.station_id
        JOIN constituencies pc ON b.pc_id = pc.constituency_id
        JOIN constituencies ac ON b.ac_id = ac.constituency_id
        WHERE v.demo_epic_no = %s;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, (clean_epic,))
            voter = cursor.fetchone()
            if voter:
                # Format dates and serializable values
                if voter.get("dob"):
                    voter["dob"] = str(voter["dob"])
            return voter

    def get_voter_by_id(self, voter_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves voter details by voter_id."""
        query = """
        SELECT
            v.voter_id,
            v.demo_epic_no,
            v.full_name,
            v.dob,
            v.gender,
            v.address_zone,
            v.pincode,
            v.special_category,
            v.priority_level,
            v.simulated_verification_status,
            v.assigned_booth_id,
            b.booth_number,
            b.booth_name,
            b.room_number,
            ps.station_name,
            pc.constituency_name AS parliamentary_constituency,
            ac.constituency_name AS assembly_constituency
        FROM voters v
        JOIN polling_booths b ON v.assigned_booth_id = b.booth_id
        JOIN polling_stations ps ON b.station_id = ps.station_id
        JOIN constituencies pc ON b.pc_id = pc.constituency_id
        JOIN constituencies ac ON b.ac_id = ac.constituency_id
        WHERE v.voter_id = %s;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, (voter_id,))
            voter = cursor.fetchone()
            if voter and voter.get("dob"):
                voter["dob"] = str(voter["dob"])
            return voter

    def list_voters(
        self,
        booth_id: Optional[int] = None,
        category: Optional[str] = None,
        verification_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Lists voters with filtering and total count."""
        where_clauses = []
        params = []

        if booth_id:
            where_clauses.append("v.assigned_booth_id = %s")
            params.append(booth_id)
        if category:
            where_clauses.append("v.special_category = %s")
            params.append(category)
        if verification_status:
            where_clauses.append("v.simulated_verification_status = %s")
            params.append(verification_status)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_query = f"SELECT COUNT(*) as total FROM voters v {where_sql};"
        data_query = f"""
        SELECT
            v.voter_id,
            v.demo_epic_no,
            v.full_name,
            v.dob,
            v.gender,
            v.address_zone,
            v.pincode,
            v.special_category,
            v.priority_level,
            v.simulated_verification_status,
            v.assigned_booth_id,
            b.booth_name,
            b.booth_number
        FROM voters v
        JOIN polling_booths b ON v.assigned_booth_id = b.booth_id
        {where_sql}
        ORDER BY v.voter_id ASC
        LIMIT %s OFFSET %s;
        """

        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(count_query, params)
            total = cursor.fetchone()["total"]

            data_params = list(params) + [limit, offset]
            cursor.execute(data_query, data_params)
            rows = cursor.fetchall()
            for r in rows:
                if r.get("dob"):
                    r["dob"] = str(r["dob"])

            return rows, total

    def register_synthetic_voter(self, voter_data: Dict[str, Any]) -> Tuple[bool, str, Optional[int]]:
        """
        Registers a new synthetic demo voter (privacy & synthetic identity compliant).
        """
        epic = voter_data.get("demo_epic_no", "").strip().upper()
        if not self.SYNTHETIC_EPIC_PATTERN.match(epic):
            return False, "INVALID_EPIC_FORMAT_MUST_BE_DEM-UK-2026-XXXX", None

        # Determine priority level based on category
        category = voter_data.get("special_category", "GENERAL").upper()
        if category in ("SENIOR_CITIZEN", "PERSON_WITH_DISABILITY", "PREGNANT_WOMEN"):
            priority_level = 1
        else:
            priority_level = 3

        insert_sql = """
        INSERT INTO voters (
            demo_epic_no, full_name, dob, gender, address_zone, pincode,
            special_category, priority_level, simulated_verification_status, assigned_booth_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'UNVERIFIED', %s);
        """
        with db_pool.get_cursor() as (conn, cursor):
            try:
                cursor.execute(insert_sql, (
                    epic,
                    voter_data["full_name"],
                    voter_data["dob"],
                    voter_data["gender"],
                    voter_data.get("address_zone", "Dehradun Zone"),
                    voter_data.get("pincode", "248001"),
                    category,
                    priority_level,
                    voter_data["assigned_booth_id"]
                ))
                conn.commit()
                new_id = cursor.lastrowid
                return True, "SUCCESS", new_id
            except Exception as e:
                logger.error("Error registering synthetic voter: %s", e)
                return False, str(e), None

# Singleton instance
voter_service = VoterService()
