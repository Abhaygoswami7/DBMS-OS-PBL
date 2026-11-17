"""
High-Concurrency Stress Test: 100 Threads Competing for 50-Seat Time Slot
Academic Verification: OS Critical Sections, ACID Mutual Exclusion & Zero Overbooking

Demonstrates:
- 100 concurrent voter threads synchronized via threading.Barrier(100) to release simultaneously.
- Competition for a single time slot with max_capacity = 50.
- Rigorous mathematical invariant verification:
    1. Exactly 50 requests receive CONFIRMED allocations (100% capacity filled).
    2. Exactly 50 requests receive SLOT_CAPACITY_EXCEEDED / REJECTED responses.
    3. Final database allocated_count strictly equals 50.
    4. Exactly 0 overbooking incidents occurred.
    5. Zero duplicate active bookings exist across any voter ID.
"""

import pytest
import threading
import time
from database.db_pool import db_pool
from backend.app.services.allocation_service import allocation_service


class TestConcurrencyStress50Cap:
    """Verifies concurrency safety under sustained high-thread contention."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown_stress_slot(self):
        """Creates or resets an isolated test time slot with max_capacity = 50."""
        self.test_booth_id = 1
        self.test_event_id = 1
        self.capacity_cap = 50
        self.total_threads = 100

        # Step 1: Clean up any old stress test artifacts
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("DELETE FROM slot_allocations WHERE booking_reference_token LIKE 'STRESS-50CAP-%';")
            # Create a dedicated stress test slot
            cursor.execute("""
                INSERT INTO time_slots (
                    booth_id, event_id, slot_date, start_time, end_time,
                    max_capacity, allocated_count, priority_reserved_capacity, status
                ) VALUES (
                    %s, %s, '2026-11-20', '16:00:00', '17:00:00', %s, 0, 10, 'OPEN'
                ) ON DUPLICATE KEY UPDATE 
                    allocated_count = 0, status = 'OPEN', max_capacity = %s;
            """, (self.test_booth_id, self.test_event_id, self.capacity_cap, self.capacity_cap))
            cursor.execute("SELECT slot_id FROM time_slots WHERE booth_id = %s AND slot_date = '2026-11-20' AND start_time = '16:00:00';", (self.test_booth_id,))
            row = cursor.fetchone()
            self.test_slot_id = row["slot_id"] if isinstance(row, dict) else row[0]
            conn.commit()

        # Step 2: Ensure 100 synthetic voters exist for this test
        with db_pool.get_cursor() as (conn, cursor):
            for i in range(1, self.total_threads + 1):
                epic = f"DEM-STRESS-50CAP-{i:04d}"
                cursor.execute("""
                    INSERT INTO voters (
                        voter_id, demo_epic_no, full_name, dob, gender, address_zone, pincode,
                        special_category, priority_level, assigned_booth_id
                    ) VALUES (
                        %s, %s, %s, '1990-01-01', 'OTHER', 'Stress Test Zone', '263136',
                        'GENERAL', 4, %s
                    ) ON DUPLICATE KEY UPDATE assigned_booth_id = %s;
                """, (9000 + i, epic, f"Stress Voter {i}", self.test_booth_id, self.test_booth_id))
            conn.commit()

        yield

        # Teardown: Clean up stress allocations, test voters, and test slot
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(f"DELETE FROM slot_allocations WHERE slot_id = {self.test_slot_id};")
            cursor.execute("DELETE FROM voters WHERE voter_id BETWEEN 9001 AND 9100;")
            cursor.execute(f"DELETE FROM time_slots WHERE slot_id = {self.test_slot_id};")
            conn.commit()

    def test_100_threads_competing_for_50_capacity_slot(self):
        """
        Launches 100 simultaneous threads against a single 50-seat slot.
        Verifies exact 50 success, 50 rejection, 0 overbooking, 0 duplicates.
        """
        barrier = threading.Barrier(self.total_threads)
        results = [None] * self.total_threads

        def worker_voter_task(index: int, voter_id: int):
            try:
                barrier.wait()
                res = allocation_service.allocate_voter_slot(
                    voter_id=voter_id,
                    booth_id=self.test_booth_id,
                    slot_id=self.test_slot_id,
                    allocation_type="USER_RESERVED"
                )
                results[index] = res
            except Exception as exc:
                results[index] = {"success": False, "status_code": "EXCEPTION", "error": str(exc)}

        threads = []
        for i in range(self.total_threads):
            v_id = 9001 + i
            t = threading.Thread(
                target=worker_voter_task,
                args=(i, v_id),
                name=f"StressThread-Voter-{v_id}"
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=15.0)

        # 1. Inspect in-memory thread responses
        success_results = [r for r in results if r and r.get("success") is True]
        failed_results = [r for r in results if r and r.get("success") is False]

        assert len(success_results) == 50, f"Expected exactly 50 successes, but got {len(success_results)}"
        assert len(failed_results) == 50, f"Expected exactly 50 rejections, but got {len(failed_results)}"

        # Verify failure reasons correspond to capacity exhaustion
        for f in failed_results:
            assert f.get("status_code") in ("SLOT_FULL", "CAPACITY_EXCEEDED", "SLOT_CAPACITY_EXCEEDED", "QUOTA_FULL")

        # 2. Inspect physical database state
        with db_pool.get_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("SELECT max_capacity, allocated_count, status FROM time_slots WHERE slot_id = %s;", (self.test_slot_id,))
            slot_row = cursor.fetchone()
            assert slot_row["allocated_count"] == 50
            assert slot_row["max_capacity"] == 50
            assert slot_row["status"] in ("FULL", "OPEN")

            cursor.execute("SELECT COUNT(*) AS cnt FROM slot_allocations WHERE slot_id = %s AND status = 'CONFIRMED';", (self.test_slot_id,))
            alloc_cnt = cursor.fetchone()["cnt"]
            assert alloc_cnt == 50

            # 3. Verify zero duplicate bookings for any voter
            cursor.execute("""
                SELECT voter_id, COUNT(*) AS voter_cnt 
                FROM slot_allocations 
                WHERE slot_id = %s AND status = 'CONFIRMED'
                GROUP BY voter_id 
                HAVING COUNT(*) > 1;
            """, (self.test_slot_id,))
            duplicates = cursor.fetchall()
            assert len(duplicates) == 0, "Zero duplicate active allocations permitted."
