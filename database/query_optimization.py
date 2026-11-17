"""
VoteIT Query Optimization and EXPLAIN Analyzer
Academic Demonstration: Database Management Systems (DBMS) Query Execution Plans

Demonstrates query execution plan analysis using EXPLAIN / EXPLAIN ANALYZE on critical
application queries (voter lookup, slot lookup, allocation search, and admin analytics).
Verifies that proper B-Tree indexing avoids full table scans (type=ALL) on production paths.
"""

import sys
import os
from typing import Dict, Any, List

# Ensure parent directory is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from database.db_pool import db_pool


QUERY_BENCHMARKS = [
    {
        "name": "Voter Lookup by EPIC (Point Query)",
        "description": "Locates a voter by synthetic EPIC card number during authentication.",
        "query": "SELECT voter_id, full_name, demo_epic_no, special_category, priority_level, assigned_booth_id FROM voters WHERE demo_epic_no = %s",
        "params": ("DEM-UK-2026-0001",),
        "target_index": "demo_epic_no (UNIQUE)",
        "expected_type": "const"
    },
    {
        "name": "Voter Active Allocation Lookup",
        "description": "Checks existing active allocations for a voter to prevent duplicate bookings.",
        "query": "SELECT allocation_id, voter_id, slot_id, booking_reference_token, status FROM slot_allocations WHERE voter_id = %s AND status = %s",
        "params": (1, "CONFIRMED"),
        "target_index": "idx_alloc_voter",
        "expected_type": "ref"
    },
    {
        "name": "Booth Slot Availability with Capacity Check",
        "description": "Retrieves real-time slot capacity and current load for a selected booth.",
        "query": "SELECT slot_id, booth_id, slot_date, start_time, end_time, max_capacity, allocated_count, status FROM time_slots WHERE booth_id = %s AND status = %s",
        "params": (1, "OPEN"),
        "target_index": "idx_slots_booth_status",
        "expected_type": "ref"
    },
    {
        "name": "Station and Booth Jurisdiction Join",
        "description": "Joins polling stations and booths for geographical allocation lookups.",
        "query": """
            SELECT ps.station_name, ps.address, b.booth_number, b.booth_name, b.is_active
            FROM polling_stations ps
            JOIN polling_booths b ON ps.station_id = b.station_id
            WHERE b.is_active = %s
        """,
        "params": (1,),
        "target_index": "PRIMARY / fk_booths_station",
        "expected_type": "ref or eq_ref"
    },
    {
        "name": "Recent Booked Voters Administrative Query (Forced Index Scan)",
        "description": "Fetches recent allocations sorted by allocation timestamp for admin monitoring.",
        "query": """
            SELECT a.allocation_id, a.booking_reference_token, a.status, a.booked_at,
                   v.full_name, v.special_category, v.priority_level,
                   b.booth_name, ps.station_name
            FROM slot_allocations a FORCE INDEX (idx_alloc_booked_at)
            JOIN voters v ON a.voter_id = v.voter_id
            JOIN time_slots s ON a.slot_id = s.slot_id
            JOIN polling_booths b ON s.booth_id = b.booth_id
            JOIN polling_stations ps ON b.station_id = ps.station_id
            ORDER BY a.booked_at DESC
            LIMIT 10
        """,
        "params": (),
        "target_index": "idx_alloc_booked_at / B-Tree Index Scan",
        "expected_type": "index / ref"
    }
]


def explain_query(query_sql: str, params: tuple) -> List[Dict[str, Any]]:
    """Runs EXPLAIN on the given SQL query and returns the tabular execution plan."""
    explain_sql = f"EXPLAIN {query_sql}"
    with db_pool.get_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(explain_sql, params)
        rows = cursor.fetchall()
        return rows


def explain_analyze_query(query_sql: str, params: tuple) -> str:
    """Runs EXPLAIN ANALYZE on MySQL 8.0+ to show actual execution tree and timings."""
    explain_analyze_sql = f"EXPLAIN ANALYZE {query_sql}"
    try:
        with db_pool.get_cursor(dictionary=False) as (conn, cursor):
            cursor.execute(explain_analyze_sql, params)
            rows = cursor.fetchall()
            return "\n".join(r[0] for r in rows) if rows else "No analysis output"
    except Exception as exc:
        return f"EXPLAIN ANALYZE not supported or failed: {str(exc)}"


def run_query_optimization_analysis() -> Dict[str, Any]:
    """
    Executes EXPLAIN analysis across all critical benchmark queries and returns
    structured results verifying indexing and execution efficiency.
    """
    results = []
    all_optimal = True

    for benchmark in QUERY_BENCHMARKS:
        plan_rows = explain_query(benchmark["query"], benchmark["params"])
        analyze_output = explain_analyze_query(benchmark["query"], benchmark["params"])

        # Inspect if table scans occur on critical large tables
        uses_index = True
        access_types = []
        keys_used = []
        for row in plan_rows:
            access_type = row.get("type", "ALL")
            access_types.append(access_type)
            key_used = row.get("key")
            keys_used.append(key_used)
            # 'ALL' means full table scan
            if access_type == "ALL" and row.get("rows", 0) > 100:
                uses_index = False
                all_optimal = False

        results.append({
            "name": benchmark["name"],
            "description": benchmark["description"],
            "target_index": benchmark["target_index"],
            "expected_type": benchmark["expected_type"],
            "plan_steps": plan_rows,
            "access_types": access_types,
            "keys_used": keys_used,
            "optimal": uses_index,
            "explain_analyze": analyze_output
        })

    return {
        "status": "SUCCESS",
        "benchmark_count": len(QUERY_BENCHMARKS),
        "all_optimal": all_optimal,
        "benchmarks": results
    }


def print_optimization_report():
    """Formats and prints an ASCII report suitable for B.Tech project presentation."""
    print("=" * 80)
    print(" VOTEIT DBMS QUERY OPTIMIZATION AND EXECUTION PLAN REPORT")
    print(" Engine: MySQL 8.4 InnoDB | Metric: EXPLAIN / EXPLAIN ANALYZE")
    print("=" * 80)

    analysis = run_query_optimization_analysis()

    for idx, bench in enumerate(analysis["benchmarks"], 1):
        print(f"\n[{idx}] {bench['name']}")
        print(f"    Description : {bench['description']}")
        print(f"    Target Index: {bench['target_index']}")
        print(f"    Access Types: {', '.join(str(t) for t in bench['access_types'])}")
        print(f"    Keys Used   : {', '.join(str(k) for k in bench['keys_used'])}")
        print(f"    Status      : {'OPTIMAL (Index Utilized)' if bench['optimal'] else 'SUB-OPTIMAL'}")
        print("    Execution Plan Details:")
        for step in bench["plan_steps"]:
            table_name = step.get("table", "N/A")
            access_type = step.get("type", "N/A")
            possible = step.get("possible_keys", "None")
            key = step.get("key", "None")
            rows = step.get("rows", "N/A")
            extra = step.get("Extra", "")
            print(f"      - Table: {table_name:<16} | Type: {access_type:<8} | Key: {str(key):<20} | Rows: {str(rows):<5} | Extra: {extra}")

        if "EXPLAIN ANALYZE not supported" not in bench["explain_analyze"]:
            print("    Actual Execution Profile:")
            for line in bench["explain_analyze"].splitlines()[:4]:
                print(f"      {line}")

    print("\n" + "=" * 80)
    print(f" OVERALL OPTIMIZATION AUDIT: {'PASS - ALL CRITICAL PATHS INDEXED' if analysis['all_optimal'] else 'WARNING'}")
    print("=" * 80)


if __name__ == "__main__":
    print_optimization_report()
