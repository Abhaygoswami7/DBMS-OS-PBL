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

    @staticmethod
    def format_aadhaar_id(raw_digits: Optional[str]) -> Optional[str]:
        """Formats 12 numeric digits into XXXX-XXXX-XXXX display format."""
        if not raw_digits:
            return None
        clean = re.sub(r"\D", "", str(raw_digits))
        if len(clean) == 12:
            return f"{clean[:4]}-{clean[4:8]}-{clean[8:]}"
        return raw_digits

    def _attach_active_booking(self, cursor, voter: Dict[str, Any]) -> Dict[str, Any]:
        """Queries and attaches active confirmed booking details if one exists for the voter."""
        if not voter or not voter.get("voter_id"):
            return voter
        alloc_query = """
        SELECT
            sa.allocation_id,
            sa.booking_reference_token,
            sa.booth_id,
            sa.slot_id,
            sa.status,
            sa.queue_token_no,
            sa.booked_at,
            ts.start_time,
            ts.end_time,
            ts.slot_date,
            b.booth_name,
            ps.station_name
        FROM slot_allocations sa
        JOIN time_slots ts ON sa.slot_id = ts.slot_id
        JOIN polling_booths b ON sa.booth_id = b.booth_id
        JOIN polling_stations ps ON b.station_id = ps.station_id
        WHERE sa.voter_id = %s AND sa.status IN ('CONFIRMED', 'CHECKED_IN')
        ORDER BY sa.allocation_id DESC
        LIMIT 1;
        """
        cursor.execute(alloc_query, (voter["voter_id"],))
        alloc = cursor.fetchone()
        if alloc:
            voter["has_active_booking"] = True
            voter["active_booking"] = {
                "allocation_id": alloc["allocation_id"],
                "booking_reference_token": alloc["booking_reference_token"],
                "booth_id": alloc["booth_id"],
                "booth_name": alloc["booth_name"],
                "station_name": alloc["station_name"],
                "slot_id": alloc["slot_id"],
                "start_time": str(alloc["start_time"]),
                "end_time": str(alloc["end_time"]),
                "slot_date": str(alloc["slot_date"]),
                "queue_token_no": alloc.get("queue_token_no", 1),
                "status": alloc["status"],
                "booked_at": str(alloc["booked_at"])
            }
        else:
            voter["has_active_booking"] = False
            voter["active_booking"] = None
        return voter

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
            v.synthetic_aadhaar_id,
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
            b.pc_id,
            b.ac_id,
            ps.station_id,
            ps.station_code,
            ps.station_name,
            ps.address AS station_address,
            ps.pincode AS station_pincode,
            ps.latitude,
            ps.longitude,
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
                if voter.get("dob"):
                    voter["dob"] = str(voter["dob"])
                if voter.get("latitude") is not None:
                    voter["latitude"] = float(voter["latitude"])
                if voter.get("longitude") is not None:
                    voter["longitude"] = float(voter["longitude"])
                voter["formatted_synthetic_aadhaar_id"] = self.format_aadhaar_id(voter.get("synthetic_aadhaar_id"))
                self._attach_active_booking(cursor, voter)
            return voter

    def get_voter_by_synthetic_aadhaar(self, synthetic_aadhaar: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves voter details by persistent 12-digit synthetic demo ID.
        Rejects unknown IDs or non-12-digit numbers. Never falls back to a default voter.
        """
        clean_digits = re.sub(r"\D", "", str(synthetic_aadhaar or ""))
        if len(clean_digits) != 12:
            logger.warning("Rejected invalid synthetic demo ID (must be exactly 12 digits): %s", synthetic_aadhaar)
            return None

        query = """
        SELECT
            v.voter_id,
            v.demo_epic_no,
            v.synthetic_aadhaar_id,
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
            b.pc_id,
            b.ac_id,
            ps.station_id,
            ps.station_code,
            ps.station_name,
            ps.address AS station_address,
            ps.pincode AS station_pincode,
            ps.latitude,
            ps.longitude,
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
        WHERE v.synthetic_aadhaar_id = %s;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, (clean_digits,))
            voter = cursor.fetchone()
            if voter:
                if voter.get("dob"):
                    voter["dob"] = str(voter["dob"])
                if voter.get("latitude") is not None:
                    voter["latitude"] = float(voter["latitude"])
                if voter.get("longitude") is not None:
                    voter["longitude"] = float(voter["longitude"])
                voter["formatted_synthetic_aadhaar_id"] = self.format_aadhaar_id(voter.get("synthetic_aadhaar_id"))
                self._attach_active_booking(cursor, voter)
            return voter

    def get_voter_by_id(self, voter_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves voter details by voter_id with complete jurisdictional mapping."""
        query = """
        SELECT
            v.voter_id,
            v.demo_epic_no,
            v.synthetic_aadhaar_id,
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
            b.pc_id,
            b.ac_id,
            ps.station_id,
            ps.station_code,
            ps.station_name,
            ps.address AS station_address,
            ps.pincode AS station_pincode,
            ps.latitude,
            ps.longitude,
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
        WHERE v.voter_id = %s;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, (voter_id,))
            voter = cursor.fetchone()
            if voter:
                if voter.get("dob"):
                    voter["dob"] = str(voter["dob"])
                if voter.get("latitude") is not None:
                    voter["latitude"] = float(voter["latitude"])
                if voter.get("longitude") is not None:
                    voter["longitude"] = float(voter["longitude"])
                voter["formatted_synthetic_aadhaar_id"] = self.format_aadhaar_id(voter.get("synthetic_aadhaar_id"))
                self._attach_active_booking(cursor, voter)
            return voter

    def list_voters(
        self,
        booth_id: Optional[int] = None,
        category: Optional[str] = None,
        verification_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Lists voters with filtering, total count, complete station coordinates and active booking flags."""
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
            v.synthetic_aadhaar_id,
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
            b.booth_number,
            b.pc_id,
            b.ac_id,
            ps.station_id,
            ps.station_name,
            ps.latitude,
            ps.longitude,
            (SELECT COUNT(*) FROM slot_allocations sa WHERE sa.voter_id = v.voter_id AND sa.status IN ('CONFIRMED', 'CHECKED_IN')) AS has_active_booking,
            (SELECT sa.booking_reference_token FROM slot_allocations sa WHERE sa.voter_id = v.voter_id AND sa.status IN ('CONFIRMED', 'CHECKED_IN') ORDER BY sa.allocation_id DESC LIMIT 1) AS active_token
        FROM voters v
        JOIN polling_booths b ON v.assigned_booth_id = b.booth_id
        JOIN polling_stations ps ON b.station_id = ps.station_id
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
                if r.get("latitude") is not None:
                    r["latitude"] = float(r["latitude"])
                if r.get("longitude") is not None:
                    r["longitude"] = float(r["longitude"])
                r["formatted_synthetic_aadhaar_id"] = self.format_aadhaar_id(r.get("synthetic_aadhaar_id"))
                r["has_active_booking"] = bool(r.get("has_active_booking", 0))

            return rows, total

    def register_synthetic_voter(self, voter_data: Dict[str, Any]) -> Tuple[bool, str, Optional[int]]:
        """
        Registers a new synthetic demo voter (privacy & synthetic identity compliant).
        """
        epic = voter_data.get("demo_epic_no", "").strip().upper()
        if not self.SYNTHETIC_EPIC_PATTERN.match(epic):
            return False, "INVALID_EPIC_FORMAT_MUST_BE_DEM-UK-2026-XXXX", None

        # Centralized project-defined priority hierarchy:
        # P1: PREGNANT_WOMEN (1), P2: PERSON_WITH_DISABILITY (2), P3: SENIOR_CITIZEN (3), P4: GENERAL (4)
        CATEGORY_PRIORITY_MAP = {
            "PREGNANT_WOMEN": 1,
            "PERSON_WITH_DISABILITY": 2,
            "SENIOR_CITIZEN": 3,
            "GENERAL": 4
        }
        category = voter_data.get("special_category", "GENERAL").upper()
        priority_level = CATEGORY_PRIORITY_MAP.get(category, 4)

        synthetic_aadhaar = voter_data.get("synthetic_aadhaar_id")
        if synthetic_aadhaar:
            synthetic_aadhaar = re.sub(r"\D", "", str(synthetic_aadhaar))

        insert_sql = """
        INSERT INTO voters (
            demo_epic_no, synthetic_aadhaar_id, full_name, dob, gender, address_zone, pincode,
            special_category, priority_level, simulated_verification_status, assigned_booth_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'UNVERIFIED', %s);
        """
        with db_pool.get_cursor() as (conn, cursor):
            try:
                cursor.execute(insert_sql, (
                    epic,
                    synthetic_aadhaar,
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
