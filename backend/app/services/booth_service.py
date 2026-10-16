"""
Polling Booth & Logistics Aggregation Service
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Handles:
  1. Booth, Station, and Constituency Lookups.
  2. Real-Time Occupancy & Utilization Monitoring via Database Views:
     - vw_booth_live_status
     - vw_constituency_logistics_summary
  3. Time Slot Inspection with OS In-Memory LRU Cache Integration.
"""

import logging
from typing import Dict, Any, Optional, List
from database.db_pool import db_pool
from backend.app.os_engine.memory_and_logger import os_lru_cache

logger = logging.getLogger("booth_service")

class BoothService:
    """Service managing polling booth logistics, slot capacities, and aggregated metrics."""

    def get_all_constituencies(self) -> List[Dict[str, Any]]:
        """Returns all Parliamentary and Assembly constituencies (cached in LRU)."""
        cache_key = "constituencies:all"
        cached = os_lru_cache.get(cache_key)
        if cached:
            return cached

        query = """
        SELECT
            c.constituency_id,
            c.constituency_code,
            c.constituency_name,
            c.constituency_type,
            c.parent_pc_id,
            c.total_registered_voters,
            s.state_code,
            s.state_name
        FROM constituencies c
        JOIN states s ON c.state_id = s.state_id
        ORDER BY c.constituency_type DESC, c.constituency_id ASC;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query)
            results = cursor.fetchall()
            os_lru_cache.put(cache_key, results)
            return results

    def get_polling_stations(self, pincode: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns polling stations with physical accessibility features."""
        cache_key = f"stations:pincode:{pincode or 'all'}"
        cached = os_lru_cache.get(cache_key)
        if cached:
            return cached

        query = """
        SELECT
            station_id,
            station_code,
            station_name,
            address,
            pincode,
            latitude,
            longitude,
            total_booths,
            has_wheelchair_ramp,
            has_separate_entry_exit
        FROM polling_stations
        """
        params = []
        if pincode:
            query += " WHERE pincode = %s"
            params.append(pincode)
        query += " ORDER BY station_id ASC;"

        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, params)
            results = cursor.fetchall()
            for r in results:
                # Convert decimal coordinates to float
                if r.get("latitude") is not None:
                    r["latitude"] = float(r["latitude"])
                if r.get("longitude") is not None:
                    r["longitude"] = float(r["longitude"])
            os_lru_cache.put(cache_key, results)
            return results

    def get_polling_booths(
        self,
        station_id: Optional[int] = None,
        pc_id: Optional[int] = None,
        ac_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Returns polling booths mapped to their station, PC, and AC."""
        where_clauses = ["b.is_active = 1"]
        params = []

        if station_id:
            where_clauses.append("b.station_id = %s")
            params.append(station_id)
        if pc_id:
            where_clauses.append("b.pc_id = %s")
            params.append(pc_id)
        if ac_id:
            where_clauses.append("b.ac_id = %s")
            params.append(ac_id)

        query = f"""
        SELECT
            b.booth_id,
            b.booth_number,
            b.booth_name,
            b.room_number,
            b.max_capacity_per_slot,
            b.evm_units_count,
            ps.station_id,
            ps.station_name,
            ps.address AS station_address,
            ps.has_wheelchair_ramp,
            pc.constituency_id AS pc_id,
            pc.constituency_code AS pc_code,
            pc.constituency_name AS parliamentary_constituency,
            ac.constituency_id AS ac_id,
            ac.constituency_code AS ac_code,
            ac.constituency_name AS assembly_constituency
        FROM polling_booths b
        JOIN polling_stations ps ON b.station_id = ps.station_id
        JOIN constituencies pc ON b.pc_id = pc.constituency_id
        JOIN constituencies ac ON b.ac_id = ac.constituency_id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY b.booth_id ASC;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, params)
            return cursor.fetchall()

    def get_time_slots_for_booth(self, booth_id: int, event_id: int = 1) -> List[Dict[str, Any]]:
        """Returns discretized time slots and live remaining capacity for a specific booth."""
        query = """
        SELECT
            ts.slot_id,
            ts.booth_id,
            ts.event_id,
            ts.slot_date,
            ts.start_time,
            ts.end_time,
            ts.max_capacity,
            ts.allocated_count,
            ts.priority_reserved_capacity,
            GREATEST(0, ts.max_capacity - ts.allocated_count) AS available_capacity,
            ROUND((ts.allocated_count / ts.max_capacity) * 100, 2) AS utilization_pct,
            ts.status
        FROM time_slots ts
        WHERE ts.booth_id = %s AND ts.event_id = %s
        ORDER BY ts.slot_date ASC, ts.start_time ASC;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, (booth_id, event_id))
            slots = cursor.fetchall()
            for s in slots:
                if s.get("slot_date"):
                    s["slot_date"] = str(s["slot_date"])
                if s.get("start_time"):
                    s["start_time"] = str(s["start_time"])
                if s.get("end_time"):
                    s["end_time"] = str(s["end_time"])
                if s.get("utilization_pct") is not None:
                    s["utilization_pct"] = float(s["utilization_pct"])
            return slots

    def get_live_booth_status(self, booth_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Queries the live operational view: vw_booth_live_status."""
        query = "SELECT * FROM vw_booth_live_status"
        params = []
        if booth_id:
            query += " WHERE booth_id = %s"
            params.append(booth_id)
        query += " ORDER BY booth_id ASC, start_time ASC;"

        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, params)
            rows = cursor.fetchall()
            for r in rows:
                if r.get("slot_date"):
                    r["slot_date"] = str(r["slot_date"])
                if r.get("start_time"):
                    r["start_time"] = str(r["start_time"])
                if r.get("end_time"):
                    r["end_time"] = str(r["end_time"])
                if r.get("capacity_utilization_pct") is not None:
                    r["capacity_utilization_pct"] = float(r["capacity_utilization_pct"])
            return rows

    def get_constituency_logistics_summary(self) -> List[Dict[str, Any]]:
        """Queries the aggregated view: vw_constituency_logistics_summary."""
        query = "SELECT * FROM vw_constituency_logistics_summary ORDER BY constituency_id ASC;"
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query)
            rows = cursor.fetchall()
            for r in rows:
                if r.get("aggregate_booking_pct") is not None:
                    r["aggregate_booking_pct"] = float(r["aggregate_booking_pct"])
            return rows

# Singleton instance
booth_service = BoothService()
