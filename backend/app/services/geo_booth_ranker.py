"""
Haversine Geolocation Booth Ranking Service
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/services/geo_booth_ranker.py

Provides:
  1. Mathematical Haversine great-circle distance calculation between voter coordinates
     and all candidate polling stations.
  2. Multi-factor filtering:
     - Simultaneous Lok Sabha (PC) and Vidhan Sabha (AC) jurisdiction match.
     - Wheelchair accessibility requirement (requires_wheelchair_accessibility).
     - Active operational status (is_active = 1).
  3. Multi-criteria composite ranking combining distance proximity and live slot availability ratio.
"""

import math
import logging
from typing import Dict, Any, Optional, List, Tuple
from database.db_pool import db_pool
from backend.app.os_engine.memory_and_logger import os_lru_cache

logger = logging.getLogger("geo_booth_ranker")

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the great-circle distance in kilometers between two GPS coordinate points
    (latitude and longitude in decimal degrees) using the mathematical Haversine formula.
    
    Formula:
      a = sin^2(delta_lat / 2) + cos(lat1) * cos(lat2) * sin^2(delta_lon / 2)
      c = 2 * atan2(sqrt(a), sqrt(1 - a))
      d = R * c  (where R = 6371.0 km)
    """
    R = 6371.0  # Earth's mean radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(R * c, 4)

class GeoBoothRanker:
    """
    Service for calculating geodesic proximity and ranking polling booths
    based on ONOE jurisdiction, physical accessibility, and live capacity ratios.
    """

    def __init__(self):
        self.default_ref_lat = 30.34215
        self.default_ref_lon = 78.02148

    def get_live_slot_availability_ratios(self, event_id: int = 1) -> Dict[int, Dict[str, Any]]:
        """
        Computes live slot capacity and availability ratios for all active booths from time_slots.
        Returns a dict mapping booth_id -> {
            'total_max_capacity': int,
            'total_allocated_count': int,
            'total_available_capacity': int,
            'availability_ratio': float (0.0 to 1.0)
        }
        """
        query = """
        SELECT
            booth_id,
            COALESCE(SUM(max_capacity), 0) AS total_max,
            COALESCE(SUM(allocated_count), 0) AS total_alloc
        FROM time_slots
        WHERE event_id = %s AND status != 'CLOSED'
        GROUP BY booth_id;
        """
        ratios = {}
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, (event_id,))
            rows = cursor.fetchall()
            for r in rows:
                b_id = r["booth_id"]
                tot_max = int(r["total_max"])
                tot_alloc = int(r["total_alloc"])
                tot_avail = max(0, tot_max - tot_alloc)
                ratio = round(tot_avail / tot_max, 4) if tot_max > 0 else 0.0
                ratios[b_id] = {
                    "total_max_capacity": tot_max,
                    "total_allocated_count": tot_alloc,
                    "total_available_capacity": tot_avail,
                    "availability_ratio": ratio
                }
        return ratios

    def rank_booths(
        self,
        user_lat: float,
        user_lon: float,
        constituency_id: Optional[int] = None,
        requires_wheelchair_accessibility: bool = False,
        pc_id: Optional[int] = None,
        ac_id: Optional[int] = None,
        event_id: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Ranks candidate polling booths using Haversine distance and multi-criteria scoring:
        1. Filters by operational status (is_active = 1).
        2. Filters by simultaneous PC and AC jurisdiction match (constituency_id, pc_id, ac_id).
        3. Filters by wheelchair accessibility ramp when requires_wheelchair_accessibility=True.
        4. Calculates exact Haversine distance in km from voter coordinates to polling station.
        5. Computes composite score: (distance_km * 2.0) - (availability_ratio * 0.5)
           Lower score indicates higher priority (closer proximity + higher slot availability).
        """
        # Fetch candidate active polling booths joined with station and constituency details
        query = """
        SELECT
            b.booth_id,
            b.booth_number,
            b.booth_name,
            b.room_number,
            b.max_capacity_per_slot,
            b.evm_units_count,
            b.is_active,
            ps.station_id,
            ps.station_code,
            ps.station_name,
            ps.address AS station_address,
            ps.pincode AS station_pincode,
            ps.latitude,
            ps.longitude,
            ps.has_wheelchair_ramp,
            ps.has_separate_entry_exit,
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
        WHERE b.is_active = 1
        ORDER BY b.booth_id ASC;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query)
            all_booths = cursor.fetchall()

        # Retrieve live availability ratios for all booths
        live_ratios = self.get_live_slot_availability_ratios(event_id=event_id)

        ranked_booths = []
        for b in all_booths:
            # 1. Operational status check
            if not b.get("is_active"):
                continue

            # 2. Simultaneous ONOE Jurisdiction match
            # If constituency_id is supplied, booth must match as either its PC or AC
            if constituency_id is not None:
                if b["pc_id"] != constituency_id and b["ac_id"] != constituency_id:
                    continue

            if pc_id is not None and b["pc_id"] != pc_id:
                continue

            if ac_id is not None and b["ac_id"] != ac_id:
                continue

            # 3. Physical Wheelchair Accessibility filter
            has_ramp = bool(b.get("has_wheelchair_ramp", 0))
            if requires_wheelchair_accessibility and not has_ramp:
                continue

            # 4. Geodesic Haversine Distance computation
            stn_lat = float(b["latitude"]) if b.get("latitude") is not None else self.default_ref_lat
            stn_lon = float(b["longitude"]) if b.get("longitude") is not None else self.default_ref_lon
            dist_km = haversine_distance_km(user_lat, user_lon, stn_lat, stn_lon)

            # 5. Live capacity metrics
            cap_info = live_ratios.get(b["booth_id"], {
                "total_max_capacity": b.get("max_capacity_per_slot", 50) * 4,
                "total_allocated_count": 0,
                "total_available_capacity": b.get("max_capacity_per_slot", 50) * 4,
                "availability_ratio": 1.0
            })
            avail_ratio = cap_info["availability_ratio"]

            # 6. Multi-criteria composite ranking score
            # Proximity is prioritized (dist_km * 2.0) while higher availability provides a bonus discount (-avail_ratio * 0.5)
            composite_score = round(dist_km * 2.0 - (avail_ratio * 0.5), 3)

            ranked_booths.append({
                "booth_id": b["booth_id"],
                "booth_number": b["booth_number"],
                "booth_name": b["booth_name"],
                "room_number": b["room_number"],
                "max_capacity_per_slot": b["max_capacity_per_slot"],
                "evm_units_count": b["evm_units_count"],
                "station_id": b["station_id"],
                "station_code": b["station_code"],
                "station_name": b["station_name"],
                "station_address": b["station_address"],
                "station_pincode": b["station_pincode"],
                "has_wheelchair_ramp": has_ramp,
                "has_separate_entry_exit": bool(b.get("has_separate_entry_exit", 0)),
                "parliamentary_constituency": b["parliamentary_constituency"],
                "assembly_constituency": b["assembly_constituency"],
                "pc_id": b["pc_id"],
                "ac_id": b["ac_id"],
                "distance_km": dist_km,
                "availability_ratio": avail_ratio,
                "total_available_capacity": cap_info["total_available_capacity"],
                "composite_score": composite_score
            })

        # Sort ascending by composite score (closest + highest availability ratio first)
        ranked_booths.sort(key=lambda x: x["composite_score"])
        return ranked_booths

# Singleton instance
geo_booth_ranker = GeoBoothRanker()
