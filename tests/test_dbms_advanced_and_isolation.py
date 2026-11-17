"""
DBMS Advanced Views, Procedures, Isolation & Query Optimization Test Suite
Academic Verification: Database Management Systems (DBMS) Principles

Tests:
1. 3NF Relational Views: vw_available_booths, vw_booth_occupancy, vw_administrative_statistics.
2. Stored Procedures: sp_check_booth_availability, sp_generate_allocation_statistics.
3. ANSI/ISO SQL Transaction Isolation Levels & Live Anomaly Experiments:
   - READ UNCOMMITTED (Dirty Read demonstration)
   - READ COMMITTED (Non-Repeatable Read demonstration)
   - REPEATABLE READ (Snapshot Isolation / MVCC verification)
   - SERIALIZABLE (Shared Lock Range / Phantom read prevention)
   - Lost Update Anomaly vs Pessimistic Row Locking (SELECT ... FOR UPDATE)
4. EXPLAIN Query Execution Plans & Index Utilization.
"""

import pytest
from database.db_pool import db_pool
from database.isolation_experiments import run_all_isolation_experiments
from database.query_optimization import run_query_optimization_analysis


class TestDBMSViewsAndProcedures:
    """Verifies MySQL 8.4 InnoDB views and stored procedures."""

    def test_vw_administrative_statistics(self):
        """Verifies vw_administrative_statistics returns correct aggregated metrics."""
        with db_pool.get_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT * FROM vw_administrative_statistics;")
            row = cursor.fetchone()
            assert row is not None
            assert row["total_registered_voters"] == 61
            assert row["total_stations"] == 4
            assert row["total_active_booths"] == 8
            assert row["total_open_slots"] == 32
            assert int(row["total_electoral_capacity"]) > 1000

    def test_vw_available_booths(self):
        """Verifies vw_available_booths returns active booths mapped to their polling stations."""
        with db_pool.get_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT * FROM vw_available_booths;")
            rows = cursor.fetchall()
            assert len(rows) >= 8
            station_names = {r["station_name"] for r in rows}
            assert "Graphic Era Hill University, Bhimtal Campus" in station_names
            assert "Woodbridge School" in station_names
            assert "Vikas Bhawan (District Development Complex)" in station_names
            assert "Nagar Palika Parishad Office, Bhimtal" in station_names

    def test_vw_booth_occupancy(self):
        """Verifies vw_booth_occupancy calculates priority category breakdown per booth."""
        with db_pool.get_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT * FROM vw_booth_occupancy;")
            rows = cursor.fetchall()
            assert len(rows) >= 8
            for r in rows:
                assert "booth_id" in r
                assert "booth_name" in r
                assert "station_name" in r
                assert "total_confirmed_bookings" in r
                assert "pregnant_women_count" in r
                assert "pwd_count" in r
                assert "senior_citizen_count" in r
                assert "general_voters_count" in r

    def test_sp_check_booth_availability(self):
        """Tests stored procedure sp_check_booth_availability for Booth ID 1 and Event ID 1."""
        with db_pool.get_cursor(dictionary=False) as (conn, cursor):
            # IN: booth_id=1, event_id=1; OUT: total_slots, open_slots, total_cap, total_alloc, remaining_cap
            args = cursor.callproc("sp_check_booth_availability", [1, 1, 0, 0, 0, 0, 0])
            total_slots = args[2]
            open_slots = args[3]
            total_cap = args[4]
            total_alloc = args[5]
            remaining_cap = args[6]

            assert total_slots == 4
            assert open_slots == 4
            assert total_cap == 200
            assert remaining_cap <= total_cap

    def test_sp_generate_allocation_statistics(self):
        """Tests stored procedure sp_generate_allocation_statistics for Event ID 1."""
        with db_pool.get_cursor(dictionary=False) as (conn, cursor):
            # IN: event_id=1; OUT: p1, p2, p3, p4, total_confirmed
            args = cursor.callproc("sp_generate_allocation_statistics", [1, 0, 0, 0, 0, 0])
            p1_count = args[1]
            p2_count = args[2]
            p3_count = args[3]
            p4_count = args[4]
            total_confirmed = args[5]

            assert total_confirmed == (p1_count + p2_count + p3_count + p4_count)
            assert total_confirmed >= 0


class TestDBMSIsolationExperiments:
    """Verifies live ANSI/ISO transaction isolation level demonstrations."""

    def test_run_all_live_isolation_experiments(self):
        """
        Executes all 5 transaction isolation experiments against live MySQL connections:
        1. Dirty Read under READ UNCOMMITTED
        2. Non-Repeatable Read under READ COMMITTED
        3. MVCC Snapshot Repeatable Read under REPEATABLE READ
        4. Serialized Locking under SERIALIZABLE
        5. Lost Update vs Pessimistic Row Locking (SELECT ... FOR UPDATE)
        """
        results = run_all_isolation_experiments()
        assert len(results) == 5

        # 1. READ UNCOMMITTED: Dirty Read demonstrated
        exp1 = results[0]
        assert exp1["isolation_level"] == "READ UNCOMMITTED"
        assert exp1["anomaly_occurred"] is True

        # 2. READ COMMITTED: Non-Repeatable Read demonstrated
        exp2 = results[1]
        assert exp2["isolation_level"] == "READ COMMITTED"
        assert exp2["values_differ"] is True

        # 3. REPEATABLE READ: MVCC Snapshot consistency verified
        exp3 = results[2]
        assert exp3["isolation_level"] == "REPEATABLE READ"
        assert exp3["snapshot_consistent"] is True

        # 4. SERIALIZABLE: Shared lock blocking writer verified
        exp4 = results[3]
        assert exp4["isolation_level"] == "SERIALIZABLE"
        assert exp4["concurrent_writer_blocked"] is True

        # 5. Lost Update vs SELECT FOR UPDATE verified
        exp5 = results[4]
        assert exp5["lost_update_prevented"] is True


class TestDBMSQueryOptimization:
    """Verifies EXPLAIN execution plans and B-Tree index utilization."""

    def test_query_optimization_indexes(self):
        """Verifies that all 5 critical application query paths utilize indices without unindexed table scans."""
        analysis = run_query_optimization_analysis()
        assert analysis["status"] == "SUCCESS"
        assert analysis["benchmark_count"] == 5
        assert analysis["all_optimal"] is True

        for b in analysis["benchmarks"]:
            assert b["optimal"] is True
            assert len(b["plan_steps"]) > 0
