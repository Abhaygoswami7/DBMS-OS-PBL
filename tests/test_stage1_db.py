"""
Stage 1 Database Verification Test Suite
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Description: Verifies the Stage 1 MySQL 8.4 InnoDB relational schema, seed data,
             views, triggers, stored procedures, ACID transaction safety, and
             high-concurrency race condition handling (zero overbooking).

Requirements verified:
  1. All 11 tables, 3 views, 3 stored procedures, and 2 triggers exist in MySQL 8.4
     and contain seeded records.
  2. sp_allocate_slot_atomic books a slot and increments time_slots.allocated_count via trigger.
  3. Duplicate active booking for the same voter is rejected (DUPLICATE_BOOKING_PREVENTED).
  4. sp_cancel_slot_atomic cancels the booking and decrements time_slots.allocated_count via trigger.
  5. 10 concurrent threads trying to book a slot with 1 remaining seat result in exactly 1 booking
     and 9 rejections (zero overbooking).
"""

import threading
import time
import pytest
from database.db_pool import db_pool

DB_NAME = "smart_poll_allocation_db"

EXPECTED_TABLES = [
    "states",
    "constituencies",
    "polling_stations",
    "polling_booths",
    "voters",
    "election_events",
    "time_slots",
    "slot_allocations",
    "simulated_verifications",
    "crowd_telemetry",
    "os_concurrency_audit"
]

EXPECTED_VIEWS = [
    "vw_booth_live_status",
    "vw_voter_appointment_slip",
    "vw_constituency_logistics_summary"
]

EXPECTED_PROCEDURES = [
    "sp_allocate_slot_atomic",
    "sp_cancel_slot_atomic",
    "sp_log_os_concurrency_event"
]

EXPECTED_TRIGGERS = [
    "trg_after_allocation_insert",
    "trg_after_allocation_update"
]


# ==============================================================================
# Helper functions for invoking Stored Procedures cleanly
# ==============================================================================

def execute_sp_allocate_slot(cursor, voter_id, booth_id, slot_id, alloc_type="USER_RESERVED"):
    """Invokes sp_allocate_slot_atomic and retrieves OUT parameters."""
    cursor.execute(
        "CALL sp_allocate_slot_atomic(%s, %s, %s, %s, @status, @token, @queue);",
        (voter_id, booth_id, slot_id, alloc_type)
    )
    cursor.execute("SELECT @status, @token, @queue;")
    row = cursor.fetchone()
    # Support both tuple/list and dict cursor
    if isinstance(row, dict):
        return row.get("@status"), row.get("@token"), row.get("@queue")
    return row[0], row[1], row[2]


def execute_sp_cancel_slot(cursor, booking_token):
    """Invokes sp_cancel_slot_atomic and retrieves OUT parameter."""
    cursor.execute("CALL sp_cancel_slot_atomic(%s, @status);", (booking_token,))
    cursor.execute("SELECT @status;")
    row = cursor.fetchone()
    if isinstance(row, dict):
        return row.get("@status")
    return row[0]


# ==============================================================================
# 1. SCHEMA INTEGRITY TESTS
# ==============================================================================

def test_all_11_tables_exist_and_have_seeded_rows():
    """Verify all 11 tables exist in MySQL 8.4 and contain seeded records."""
    with db_pool.get_cursor() as (conn, cursor):
        # 1. Verify existence in information_schema
        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE';
            """,
            (DB_NAME,)
        )
        existing_tables = {r["TABLE_NAME"] if isinstance(r, dict) else r[0] for r in cursor.fetchall()}
        
        for table in EXPECTED_TABLES:
            assert table in existing_tables, f"Expected table '{table}' missing in {DB_NAME}"

        # 2. Verify all 11 tables have seeded records (count > 0)
        table_counts = {}
        for table in EXPECTED_TABLES:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table}`;")
            res = cursor.fetchone()
            count = res["cnt"] if isinstance(res, dict) else res[0]
            table_counts[table] = count
            assert count > 0, f"Table '{table}' has 0 rows; expected seeded demo records."

        print(f"\n[+] Verified all 11 tables with row counts: {table_counts}")


def test_all_3_views_exist_and_return_rows():
    """Verify all 3 reporting views exist in MySQL 8.4 and return seeded data."""
    with db_pool.get_cursor() as (conn, cursor):
        # 1. Verify existence in information_schema
        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM information_schema.VIEWS
            WHERE TABLE_SCHEMA = %s;
            """,
            (DB_NAME,)
        )
        existing_views = {r["TABLE_NAME"] if isinstance(r, dict) else r[0] for r in cursor.fetchall()}

        for view in EXPECTED_VIEWS:
            assert view in existing_views, f"Expected view '{view}' missing in {DB_NAME}"

        # 2. Verify views return rows
        for view in EXPECTED_VIEWS:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM `{view}`;")
            res = cursor.fetchone()
            count = res["cnt"] if isinstance(res, dict) else res[0]
            assert count > 0, f"View '{view}' returned 0 rows."


def test_all_3_stored_procedures_exist():
    """Verify all 3 stored procedures exist in MySQL 8.4."""
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute(
            """
            SELECT ROUTINE_NAME
            FROM information_schema.ROUTINES
            WHERE ROUTINE_SCHEMA = %s AND ROUTINE_TYPE = 'PROCEDURE';
            """,
            (DB_NAME,)
        )
        existing_procs = {r["ROUTINE_NAME"] if isinstance(r, dict) else r[0] for r in cursor.fetchall()}

        for proc in EXPECTED_PROCEDURES:
            assert proc in existing_procs, f"Expected stored procedure '{proc}' missing in {DB_NAME}"


def test_all_2_triggers_exist():
    """Verify both integrity triggers exist in MySQL 8.4."""
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute(
            """
            SELECT TRIGGER_NAME
            FROM information_schema.TRIGGERS
            WHERE TRIGGER_SCHEMA = %s;
            """,
            (DB_NAME,)
        )
        existing_triggers = {r["TRIGGER_NAME"] if isinstance(r, dict) else r[0] for r in cursor.fetchall()}

        for trigger in EXPECTED_TRIGGERS:
            assert trigger in existing_triggers, f"Expected trigger '{trigger}' missing in {DB_NAME}"


# ==============================================================================
# 2. STORED PROCEDURE & TRIGGER TRANSACTIONAL WORKFLOW TESTS
# ==============================================================================

def test_sp_allocate_slot_atomic_and_trigger_increment():
    """
    Verify sp_allocate_slot_atomic:
      1. Successfully reserves a time slot.
      2. Generates a synthetic cryptographic booking token and queue token.
      3. Fires trigger trg_after_allocation_insert to increment time_slots.allocated_count.
    """
    # Create an isolated test voter for this test
    test_epic = f"DEM-TEST-ALLOC-{int(time.time() * 1000) % 100000}"
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO voters (demo_epic_no, full_name, dob, gender, address_zone, pincode,
                                special_category, priority_level, assigned_booth_id)
            VALUES (%s, 'Stage1 Test Voter', '1992-05-10', 'FEMALE', 'Zone 1', '248003',
                    'GENERAL', 3, 1);
            """,
            (test_epic,)
        )
        conn.commit()
        voter_id = cursor.lastrowid

    try:
        booth_id = 1
        slot_id = 1

        # Check initial slot count
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("SELECT allocated_count, max_capacity FROM time_slots WHERE slot_id = %s;", (slot_id,))
            slot_info = cursor.fetchone()
            initial_count = slot_info["allocated_count"] if isinstance(slot_info, dict) else slot_info[0]

        # Allocate slot atomically
        with db_pool.get_cursor() as (conn, cursor):
            status, token, queue = execute_sp_allocate_slot(cursor, voter_id, booth_id, slot_id, "USER_RESERVED")
            conn.commit()

        assert status == "SUCCESS", f"Expected SUCCESS but got {status}"
        assert token is not None and token.startswith("TKN-UK-"), f"Invalid token format: {token}"
        assert queue > 0, f"Invalid queue number: {queue}"

        # Verify time_slots.allocated_count incremented by 1 via trigger
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("SELECT allocated_count FROM time_slots WHERE slot_id = %s;", (slot_id,))
            res = cursor.fetchone()
            new_count = res["allocated_count"] if isinstance(res, dict) else res[0]
            assert new_count == initial_count + 1, f"Expected count {initial_count + 1}, got {new_count}"

            # Verify slot_allocations record is CONFIRMED
            cursor.execute("SELECT status, queue_token_no FROM slot_allocations WHERE booking_reference_token = %s;", (token,))
            alloc_record = cursor.fetchone()
            alloc_status = alloc_record["status"] if isinstance(alloc_record, dict) else alloc_record[0]
            assert alloc_status == "CONFIRMED"

        # Cleanup booking
        with db_pool.get_cursor() as (conn, cursor):
            execute_sp_cancel_slot(cursor, token)
            conn.commit()

    finally:
        # Cleanup voter
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("DELETE FROM slot_allocations WHERE voter_id = %s;", (voter_id,))
            cursor.execute("DELETE FROM voters WHERE voter_id = %s;", (voter_id,))
            conn.commit()


def test_duplicate_active_booking_rejected():
    """Verify duplicate active booking for the same voter in the same election is rejected."""
    test_epic = f"DEM-TEST-DUP-{int(time.time() * 1000) % 100000}"
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO voters (demo_epic_no, full_name, dob, gender, address_zone, pincode,
                                special_category, priority_level, assigned_booth_id)
            VALUES (%s, 'Duplicate Test Voter', '1988-08-20', 'MALE', 'Zone 1', '248003',
                    'GENERAL', 3, 1);
            """,
            (test_epic,)
        )
        conn.commit()
        voter_id = cursor.lastrowid

    first_token = None
    try:
        booth_id = 1
        slot_id = 2

        # Step 1: Initial successful booking
        with db_pool.get_cursor() as (conn, cursor):
            status1, first_token, queue1 = execute_sp_allocate_slot(cursor, voter_id, booth_id, slot_id)
            conn.commit()
        assert status1 == "SUCCESS"

        # Step 2: Attempt duplicate active booking on same slot
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("SELECT allocated_count FROM time_slots WHERE slot_id = %s;", (slot_id,))
            count_before_dup = cursor.fetchone()
            cnt_before = count_before_dup["allocated_count"] if isinstance(count_before_dup, dict) else count_before_dup[0]

            status2, token2, queue2 = execute_sp_allocate_slot(cursor, voter_id, booth_id, slot_id)
            conn.commit()

            assert status2 == "DUPLICATE_BOOKING_PREVENTED", f"Expected DUPLICATE_BOOKING_PREVENTED, got: {status2}"
            assert token2 is None, f"Expected token to be None on duplicate rejection, got: {token2}"

            # Verify allocated_count was NOT incremented
            cursor.execute("SELECT allocated_count FROM time_slots WHERE slot_id = %s;", (slot_id,))
            count_after_dup = cursor.fetchone()
            cnt_after = count_after_dup["allocated_count"] if isinstance(count_after_dup, dict) else count_after_dup[0]
            assert cnt_after == cnt_before, "Slot count was erroneously modified on duplicate rejection!"

        # Step 3: Attempt duplicate active booking on a DIFFERENT slot in same election event
        with db_pool.get_cursor() as (conn, cursor):
            status3, token3, queue3 = execute_sp_allocate_slot(cursor, voter_id, booth_id, 3)
            conn.commit()
            assert status3 == "DUPLICATE_BOOKING_PREVENTED", f"Expected DUPLICATE_BOOKING_PREVENTED on different slot, got: {status3}"

    finally:
        with db_pool.get_cursor() as (conn, cursor):
            if first_token:
                execute_sp_cancel_slot(cursor, first_token)
            cursor.execute("DELETE FROM slot_allocations WHERE voter_id = %s;", (voter_id,))
            cursor.execute("DELETE FROM voters WHERE voter_id = %s;", (voter_id,))
            conn.commit()


def test_sp_cancel_slot_atomic_and_trigger_decrement():
    """
    Verify sp_cancel_slot_atomic:
      1. Cancels a confirmed booking.
      2. Fires trigger trg_after_allocation_update to decrement time_slots.allocated_count.
      3. Updates slot_allocations status to 'CANCELLED'.
    """
    test_epic = f"DEM-TEST-CANCEL-{int(time.time() * 1000) % 100000}"
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO voters (demo_epic_no, full_name, dob, gender, address_zone, pincode,
                                special_category, priority_level, assigned_booth_id)
            VALUES (%s, 'Cancel Test Voter', '1995-12-01', 'FEMALE', 'Zone 1', '248003',
                    'GENERAL', 3, 1);
            """,
            (test_epic,)
        )
        conn.commit()
        voter_id = cursor.lastrowid

    try:
        booth_id = 1
        slot_id = 3

        # Book slot
        with db_pool.get_cursor() as (conn, cursor):
            status, token, queue = execute_sp_allocate_slot(cursor, voter_id, booth_id, slot_id)
            conn.commit()
        assert status == "SUCCESS"

        # Record count after booking
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("SELECT allocated_count FROM time_slots WHERE slot_id = %s;", (slot_id,))
            res = cursor.fetchone()
            booked_count = res["allocated_count"] if isinstance(res, dict) else res[0]

        # Cancel slot
        with db_pool.get_cursor() as (conn, cursor):
            cancel_status = execute_sp_cancel_slot(cursor, token)
            conn.commit()

        assert cancel_status == "SUCCESS", f"Expected SUCCESS, got: {cancel_status}"

        # Verify time_slots.allocated_count decremented by 1 via trigger
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("SELECT allocated_count FROM time_slots WHERE slot_id = %s;", (slot_id,))
            res = cursor.fetchone()
            cancelled_count = res["allocated_count"] if isinstance(res, dict) else res[0]
            assert cancelled_count == booked_count - 1, (
                f"Expected count {booked_count - 1}, but got {cancelled_count}"
            )

            # Verify slot_allocations record status is 'CANCELLED'
            cursor.execute("SELECT status FROM slot_allocations WHERE booking_reference_token = %s;", (token,))
            res = cursor.fetchone()
            record_status = res["status"] if isinstance(res, dict) else res[0]
            assert record_status == "CANCELLED"

    finally:
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("DELETE FROM slot_allocations WHERE voter_id = %s;", (voter_id,))
            cursor.execute("DELETE FROM voters WHERE voter_id = %s;", (voter_id,))
            conn.commit()


# ==============================================================================
# 3. HIGH-CONCURRENCY RACE CONDITION TEST (ZERO OVERBOOKING)
# ==============================================================================

def test_10_concurrent_threads_one_seat_zero_overbooking():
    """
    Stress-tests MySQL 8.4 InnoDB Row-Level Locking (SELECT ... FOR UPDATE) inside
    sp_allocate_slot_atomic under severe race conditions:
      - Slot has EXACTLY 1 remaining seat (max_capacity=1, allocated_count=0).
      - 10 concurrent OS worker threads simultaneously attempt to book the seat.
      - A threading.Barrier synchronizes all 10 threads to hit the DB concurrently.
      - Result: EXACTLY 1 thread succeeds (SUCCESS) and EXACTLY 9 threads fail
        (SLOT_CAPACITY_EXCEEDED).
      - Zero overbooking occurs: allocated_count reaches exactly 1 and status becomes 'FULL'.
    """
    test_slot_id = 999
    num_threads = 10
    voter_ids = []

    # Setup isolated test slot and 10 test voters
    with db_pool.get_cursor() as (conn, cursor):
        # Clean any leftover test data
        cursor.execute("DELETE FROM slot_allocations WHERE slot_id = %s;", (test_slot_id,))
        cursor.execute("DELETE FROM time_slots WHERE slot_id = %s;", (test_slot_id,))
        cursor.execute("DELETE FROM voters WHERE demo_epic_no LIKE 'DEM-CONC-TEST-%';")

        # Create slot with max_capacity = 1, allocated_count = 0 (1 seat available)
        cursor.execute(
            """
            INSERT INTO time_slots (slot_id, booth_id, event_id, slot_date, start_time,
                                    end_time, max_capacity, allocated_count,
                                    priority_reserved_capacity, status)
            VALUES (%s, 1, 1, '2026-11-25', '14:00:00', '15:00:00', 1, 0, 0, 'OPEN');
            """,
            (test_slot_id,)
        )

        # Create 10 distinct voters assigned to booth 1
        for i in range(1, num_threads + 1):
            epic = f"DEM-CONC-TEST-{i:03d}"
            cursor.execute(
                """
                INSERT INTO voters (demo_epic_no, full_name, dob, gender, address_zone, pincode,
                                    special_category, priority_level, assigned_booth_id)
                VALUES (%s, %s, '1990-01-01', 'OTHER', 'Zone Test', '248001', 'GENERAL', 3, 1);
                """,
                (epic, f"Concurrent Voter {i}")
            )
            voter_ids.append(cursor.lastrowid)

        conn.commit()

    results = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(num_threads)

    def worker(v_id):
        # Fresh connection per thread to simulate independent concurrent transactions
        with db_pool.get_connection() as c:
            cur = c.cursor()
            # Wait for all 10 threads to arrive at barrier before firing
            barrier.wait()
            try:
                cur.execute(
                    "CALL sp_allocate_slot_atomic(%s, 1, %s, %s, @status, @token, @queue);",
                    (v_id, test_slot_id, "USER_RESERVED")
                )
                cur.execute("SELECT @status, @token, @queue;")
                res = cur.fetchone()
                status_code = res[0]
                token = res[1]
                queue = res[2]
                c.commit()
                with results_lock:
                    results.append((v_id, status_code, token, queue))
            except Exception as e:
                with results_lock:
                    results.append((v_id, f"EXCEPTION: {e}", None, 0))
            finally:
                cur.close()

    # Launch 10 worker threads
    threads = [threading.Thread(target=worker, args=(v_id,)) for v_id in voter_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Analyze outcomes
    assert len(results) == num_threads, f"Expected {num_threads} results, got {len(results)}"

    successes = [r for r in results if r[1] == "SUCCESS"]
    rejections = [r for r in results if r[1] == "SLOT_CAPACITY_EXCEEDED"]

    print("\n--- Concurrency Test Breakdown ---")
    for r in results:
        print(f"  Voter {r[0]}: status={r[1]}, token={r[2]}")

    # Strict assertion: Exactly 1 winner, exactly 9 rejections
    assert len(successes) == 1, (
        f"CRITICAL OVERBOOKING BUG: Expected exactly 1 SUCCESS, but got {len(successes)}!"
    )
    assert len(rejections) == 9, (
        f"Expected exactly 9 SLOT_CAPACITY_EXCEEDED, but got {len(rejections)} ({results})"
    )

    # Verify database state in time_slots
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute("SELECT allocated_count, max_capacity, status FROM time_slots WHERE slot_id = %s;", (test_slot_id,))
        final_slot = cursor.fetchone()
        final_alloc = final_slot["allocated_count"] if isinstance(final_slot, dict) else final_slot[0]
        max_cap = final_slot["max_capacity"] if isinstance(final_slot, dict) else final_slot[1]
        slot_st = final_slot["status"] if isinstance(final_slot, dict) else final_slot[2]

        assert final_alloc == 1, f"Expected allocated_count=1, got {final_alloc}"
        assert slot_st == "FULL", f"Expected slot status='FULL', got '{slot_st}'"

        # Verify exactly 1 CONFIRMED allocation in slot_allocations
        cursor.execute("SELECT COUNT(*) as cnt FROM slot_allocations WHERE slot_id = %s AND status = 'CONFIRMED';", (test_slot_id,))
        confirmed_allocs = cursor.fetchone()
        conf_count = confirmed_allocs["cnt"] if isinstance(confirmed_allocs, dict) else confirmed_allocs[0]
        assert conf_count == 1, f"Expected exactly 1 confirmed allocation record, got {conf_count}"

        # Teardown test artifacts
        cursor.execute("DELETE FROM slot_allocations WHERE slot_id = %s;", (test_slot_id,))
        cursor.execute("DELETE FROM time_slots WHERE slot_id = %s;", (test_slot_id,))
        cursor.execute("DELETE FROM voters WHERE demo_epic_no LIKE 'DEM-CONC-TEST-%';")
        conn.commit()

    print(f"[+] Concurrency test PASSED: 1 booking confirmed, 9 safely rejected, zero overbooking.")
