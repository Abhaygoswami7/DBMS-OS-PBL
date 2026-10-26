"""
Core Time-Slot Allocation, Concurrency & Scheduling Service
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Coordinates:
  1. OS Process Control Block (PCB) lifecycle transitions.
  2. CPU Request Scheduler (FCFS / Priority Scheduling with Aging).
  3. Per-Slot Mutex & Bounded Semaphore Critical Sections.
  4. Deadlock-free dual-slot reallocation (Resource Hierarchical Ordering).
  5. MySQL 8.0+ Stored Procedures (sp_allocate_slot_atomic, sp_cancel_slot_atomic).
  6. Appointment pass generation via vw_voter_appointment_slip.
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple, List
from database.db_pool import db_pool
from backend.app.os_engine.process_lifecycle import RequestPCB, ProcessState
from backend.app.os_engine.request_scheduler import os_scheduler
from backend.app.os_engine.synchronization import sync_manager
from backend.app.os_engine.memory_and_logger import os_file_logger, os_lru_cache

logger = logging.getLogger("allocation_service")

def _extract_proc_args(result_args) -> List[Any]:
    """Handles both dict (mysql-connector 26+) and tuple/list (standard) callproc returns."""
    if isinstance(result_args, dict):
        return [v for k, v in sorted(result_args.items())]
    return list(result_args)

class AllocationService:
    """Core logistical allocation orchestrator linking OS Concurrency Engine to MySQL 3NF layer."""

    # -------------------------------------------------------------------------
    # 0. POLLING HOURS DISCRETIZATION & CAPACITY SETUP
    # -------------------------------------------------------------------------
    def discretize_polling_hours(
        self,
        booth_id: int,
        event_id: int = 1,
        slot_date: Optional[str] = None,
        max_capacity_per_slot: int = 60,
        priority_reserved_capacity: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Discretizes polling hours into arrival time slots in MySQL `time_slots` table.
        Default standard ONOE schedule:
          - Slot 1: 07:00:00 - 09:30:00 (Early Morning / Priority Quota)
          - Slot 2: 09:30:00 - 12:00:00 (Late Morning Peak)
          - Slot 3: 12:30:00 - 15:00:00 (Afternoon Staggered)
          - Slot 4: 15:00:00 - 17:30:00 (Evening Pre-Close)
        Enforces strict database-level capacity and reserved quotas.
        """
        if not slot_date:
            with db_pool.get_cursor() as (conn, cursor):
                cursor.execute("SELECT election_date FROM election_events WHERE event_id = %s;", (event_id,))
                row = cursor.fetchone()
                slot_date = str(row["election_date"]) if row else "2026-11-15"

        default_windows = [
            ("07:00:00", "09:30:00"),
            ("09:30:00", "12:00:00"),
            ("12:30:00", "15:00:00"),
            ("15:00:00", "17:30:00")
        ]

        created_slots = []
        with db_pool.get_cursor() as (conn, cursor):
            for start_t, end_t in default_windows:
                insert_sql = """
                INSERT INTO time_slots
                (booth_id, event_id, slot_date, start_time, end_time, max_capacity, allocated_count, priority_reserved_capacity, status)
                VALUES (%s, %s, %s, %s, %s, %s, 0, %s, 'OPEN')
                ON DUPLICATE KEY UPDATE
                    max_capacity = VALUES(max_capacity),
                    priority_reserved_capacity = VALUES(priority_reserved_capacity);
                """
                cursor.execute(insert_sql, (
                    booth_id, event_id, slot_date, start_t, end_t,
                    max_capacity_per_slot, priority_reserved_capacity
                ))
            conn.commit()

            cursor.execute(
                """
                SELECT slot_id, booth_id, event_id, slot_date, start_time, end_time,
                       max_capacity, allocated_count, priority_reserved_capacity, status
                FROM time_slots
                WHERE booth_id = %s AND event_id = %s AND slot_date = %s
                ORDER BY start_time ASC;
                """,
                (booth_id, event_id, slot_date)
            )
            rows = cursor.fetchall()
            for r in rows:
                if r.get("slot_date"):
                    r["slot_date"] = str(r["slot_date"])
                if r.get("start_time"):
                    r["start_time"] = str(r["start_time"])
                if r.get("end_time"):
                    r["end_time"] = str(r["end_time"])
                created_slots.append(r)

        return created_slots

    def verify_capacity_invariant(self, slot_id: int) -> Dict[str, Any]:
        """
        Validates the ACID capacity invariant: allocated_count <= max_capacity (+ priority_reserved_capacity).
        Ensures no overbooking or race condition has breached limits in MySQL.
        """
        query = """
        SELECT
            slot_id, booth_id, max_capacity, allocated_count, priority_reserved_capacity, status
        FROM time_slots
        WHERE slot_id = %s;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, (slot_id,))
            slot = cursor.fetchone()
            if not slot:
                return {"invariant_satisfied": False, "error": "SLOT_NOT_FOUND"}

            allocated = int(slot["allocated_count"])
            max_cap = int(slot["max_capacity"])
            priority_cap = int(slot["priority_reserved_capacity"])
            hard_limit = max_cap + priority_cap

            cursor.execute(
                """
                SELECT COUNT(*) as active_allocations
                FROM slot_allocations
                WHERE slot_id = %s AND status IN ('CONFIRMED', 'CHECKED_IN');
                """,
                (slot_id,)
            )
            actual_alloc = cursor.fetchone()["active_allocations"]

            invariant_satisfied = (allocated <= hard_limit) and (allocated == actual_alloc)

            return {
                "slot_id": slot_id,
                "invariant_satisfied": invariant_satisfied,
                "allocated_count": allocated,
                "active_allocations_count": actual_alloc,
                "max_capacity": max_cap,
                "priority_reserved_capacity": priority_cap,
                "hard_limit": hard_limit,
                "remaining_standard_capacity": max(0, max_cap - allocated),
                "status": slot["status"]
            }

    # -------------------------------------------------------------------------
    # 1. ATOMIC SLOT ALLOCATION (Thread-Safe Critical Section)
    # -------------------------------------------------------------------------
    def allocate_voter_slot(
        self,
        voter_id: int,
        booth_id: int,
        slot_id: int,
        allocation_type: str = "USER_RESERVED"
    ) -> Dict[str, Any]:
        """
        Executes a concurrency-safe time-slot allocation:
        1. Initializes and enqueues RequestPCB into the OS scheduler.
        2. Dispatches PCB according to active policy (FCFS or Priority Aging).
        3. Enters per-slot critical section (Bounded Semaphore + RLock).
        4. Calls stored procedure sp_allocate_slot_atomic (ACID row-level X-lock).
        5. Records complete OS telemetry in the response.
        """
        # Step A: Fetch voter's priority category for PCB initialization
        voter_category = "GENERAL"
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("SELECT special_category FROM voters WHERE voter_id = %s;", (voter_id,))
            v_row = cursor.fetchone()
            if v_row and v_row.get("special_category"):
                voter_category = v_row["special_category"]

        # Step B: OS Process Creation
        pcb = RequestPCB(
            voter_id=voter_id,
            operation_type="ALLOCATE",
            priority_category=voter_category,
            resources_requested=[booth_id, slot_id]
        )

        # Step C: CPU Scheduler Enqueue & Dispatch
        os_scheduler.enqueue(pcb)
        dispatched_pcb = os_scheduler.dispatch_next() or pcb

        status_code = "UNKNOWN"
        booking_token = None
        queue_token = 0
        appointment_slip = None

        # Step D: Enter Synchronization Critical Section
        try:
            with sync_manager.critical_section_lock(dispatched_pcb, slot_id, booth_id):
                # Step E: Call MySQL Atomic Stored Procedure
                with db_pool.get_cursor() as (conn, cursor):
                    # MySQL Stored Procedure Signature:
                    # sp_allocate_slot_atomic(IN p_voter_id, IN p_booth_id, IN p_slot_id,
                    #                         IN p_allocation_type, OUT p_status, OUT p_token, OUT p_queue)
                    args = [voter_id, booth_id, slot_id, allocation_type, None, None, None]
                    raw_args = cursor.callproc("sp_allocate_slot_atomic", args)
                    conn.commit()

                    result_args = _extract_proc_args(raw_args)
                    status_code = result_args[4]
                    booking_token = result_args[5]
                    queue_token = result_args[6]

            # Invalidate booth LRU cache on successful allocation and generate appointment pass slip
            if status_code == "SUCCESS":
                os_lru_cache.invalidate()
                appointment_slip = self.get_voter_appointment_slip(booking_reference_token=booking_token)
                dispatched_pcb.transition_to(
                    ProcessState.TERMINATED,
                    f"Allocation committed successfully. Token: {booking_token}"
                )
                os_file_logger.log_trace(
                    event_type="ALLOCATION_COMMITTED",
                    pcb_dict=dispatched_pcb.to_dict(),
                    message=f"Voter {voter_id} allocated slot {slot_id} (Token: {booking_token})"
                )
            else:
                dispatched_pcb.transition_to(
                    ProcessState.TERMINATED,
                    f"Allocation rejected: {status_code}"
                )
                os_file_logger.log_trace(
                    event_type="ALLOCATION_REJECTED",
                    pcb_dict=dispatched_pcb.to_dict(),
                    message=f"Allocation rejected for voter {voter_id}: {status_code}"
                )

        except TimeoutError as te:
            status_code = "CONCURRENCY_LOCK_TIMEOUT"
            dispatched_pcb.transition_to(ProcessState.TERMINATED, str(te))
            os_file_logger.log_trace(
                event_type="LOCK_TIMEOUT_ERROR",
                pcb_dict=dispatched_pcb.to_dict(),
                message=str(te)
            )
        except Exception as e:
            logger.error("Unexpected allocation error: %s", e)
            status_code = "INTERNAL_CONCURRENCY_ERROR"
            dispatched_pcb.transition_to(ProcessState.TERMINATED, str(e))

        return {
            "success": status_code == "SUCCESS",
            "status_code": status_code,
            "booking_reference_token": booking_token,
            "queue_token_no": queue_token,
            "appointment_slip": appointment_slip,
            "pcb_telemetry": dispatched_pcb.to_dict()
        }

    # -------------------------------------------------------------------------
    # 2. ATOMIC CANCELLATION
    # -------------------------------------------------------------------------
    def cancel_slot_allocation(self, booking_reference_token: str) -> Dict[str, Any]:
        """
        Cancels an existing slot reservation via sp_cancel_slot_atomic.
        Frees slot capacity atomically and updates the allocation record.
        """
        pcb = RequestPCB(
            operation_type="CANCEL",
            priority_category="GENERAL"
        )
        pcb.transition_to(ProcessState.RUNNING, f"Cancelling token: {booking_reference_token}")

        status_code = "UNKNOWN"
        try:
            with db_pool.get_cursor() as (conn, cursor):
                args = [booking_reference_token, None]
                raw_args = cursor.callproc("sp_cancel_slot_atomic", args)
                conn.commit()
                result_args = _extract_proc_args(raw_args)
                status_code = result_args[1]

            if status_code == "SUCCESS":
                os_lru_cache.invalidate()
                pcb.transition_to(ProcessState.TERMINATED, "Cancellation committed")
                os_file_logger.log_trace(
                    event_type="CANCELLATION_COMMITTED",
                    pcb_dict=pcb.to_dict(),
                    message=f"Cancelled booking token {booking_reference_token}"
                )
            else:
                pcb.transition_to(ProcessState.TERMINATED, f"Cancellation failed: {status_code}")

        except Exception as e:
            logger.error("Cancellation error: %s", e)
            status_code = "CANCELLATION_FAILED"
            pcb.transition_to(ProcessState.TERMINATED, str(e))

        return {
            "success": status_code == "SUCCESS",
            "status_code": status_code,
            "pcb_telemetry": pcb.to_dict()
        }

    # -------------------------------------------------------------------------
    # 3. DEADLOCK-FREE DUAL SLOT REALLOCATION
    # -------------------------------------------------------------------------
    def reallocate_voter_slot(
        self,
        voter_id: int,
        booth_id: int,
        old_slot_id: int,
        new_slot_id: int,
        booking_reference_token: str
    ) -> Dict[str, Any]:
        """
        Safely swaps a voter from old_slot_id to new_slot_id.
        Eliminates Coffman Condition #4 (Circular Wait) by acquiring locks in
        strict ascending numerical order: min(old, new) -> max(old, new).
        """
        pcb = RequestPCB(
            voter_id=voter_id,
            operation_type="REALLOCATE",
            priority_category="GENERAL",
            resources_requested=[booth_id, old_slot_id, new_slot_id]
        )
        os_scheduler.enqueue(pcb)
        dispatched_pcb = os_scheduler.dispatch_next() or pcb

        status_code = "UNKNOWN"
        new_token = None
        new_queue_no = 0

        try:
            # Acquire dual locks in strict ascending order
            with sync_manager.acquire_dual_slot_locks(dispatched_pcb, old_slot_id, new_slot_id, booth_id):
                with db_pool.get_cursor() as (conn, cursor):
                    # 1. Cancel old slot
                    cancel_args = [booking_reference_token, None]
                    raw_cancel = cursor.callproc("sp_cancel_slot_atomic", cancel_args)
                    cancel_res = _extract_proc_args(raw_cancel)
                    if cancel_res[1] != "SUCCESS":
                        conn.rollback()
                        status_code = f"OLD_SLOT_CANCEL_FAILED_{cancel_res[1]}"
                    else:
                        # 2. Allocate new slot
                        alloc_args = [voter_id, booth_id, new_slot_id, "USER_RESERVED", None, None, None]
                        raw_alloc = cursor.callproc("sp_allocate_slot_atomic", alloc_args)
                        alloc_res = _extract_proc_args(raw_alloc)
                        if alloc_res[4] == "SUCCESS":
                            conn.commit()
                            status_code = "SUCCESS"
                            new_token = alloc_res[5]
                            new_queue_no = alloc_res[6]
                            os_lru_cache.invalidate()
                        else:
                            # Revert cancellation if new allocation fails
                            conn.rollback()
                            status_code = f"NEW_SLOT_ALLOC_FAILED_{alloc_res[4]}"

            dispatched_pcb.transition_to(
                ProcessState.TERMINATED,
                f"Reallocation completed: {status_code}"
            )
            os_file_logger.log_trace(
                event_type="REALLOCATION_FINISHED",
                pcb_dict=dispatched_pcb.to_dict(),
                message=f"Reallocated voter {voter_id} from {old_slot_id} to {new_slot_id} ({status_code})"
            )

        except TimeoutError as te:
            status_code = "DEADLOCK_PREVENTION_LOCK_TIMEOUT"
            dispatched_pcb.transition_to(ProcessState.TERMINATED, str(te))
        except Exception as e:
            logger.error("Reallocation exception: %s", e)
            status_code = "REALLOCATION_ERROR"
            dispatched_pcb.transition_to(ProcessState.TERMINATED, str(e))

        return {
            "success": status_code == "SUCCESS",
            "status_code": status_code,
            "new_booking_reference_token": new_token,
            "new_queue_token_no": new_queue_no,
            "pcb_telemetry": dispatched_pcb.to_dict()
        }

    # -------------------------------------------------------------------------
    # 4. VOTER APPOINTMENT PASS SLIP
    # -------------------------------------------------------------------------
    def get_voter_appointment_slip(
        self,
        booking_reference_token: Optional[str] = None,
        voter_id: Optional[int] = None,
        allocation_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Queries vw_voter_appointment_slip for verified digital appointment pass generation."""
        query = "SELECT * FROM vw_voter_appointment_slip"
        params = []
        if booking_reference_token:
            query += " WHERE booking_reference_token = %s"
            params.append(booking_reference_token)
        elif allocation_id:
            query += " WHERE allocation_id = %s"
            params.append(allocation_id)
        elif voter_id:
            query += " WHERE voter_id = %s"
            params.append(voter_id)
        else:
            return None

        query += " ORDER BY allocation_id DESC LIMIT 1;"

        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, params)
            slip = cursor.fetchone()
            if slip:
                if slip.get("booked_at"):
                    slip["booked_at"] = str(slip["booked_at"])
                if slip.get("slot_date"):
                    slip["slot_date"] = str(slip["slot_date"])
                if slip.get("start_time"):
                    slip["start_time"] = str(slip["start_time"])
                if slip.get("end_time"):
                    slip["end_time"] = str(slip["end_time"])
                if slip.get("election_date"):
                    slip["election_date"] = str(slip["election_date"])
            return slip

    # -------------------------------------------------------------------------
    # 5. OS CONCURRENCY AUDIT LOGS & SYSTEM METRICS
    # -------------------------------------------------------------------------
    def get_concurrency_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Queries the MySQL os_concurrency_audit table for real-time thread inspection."""
        query = """
        SELECT
            audit_id,
            thread_name,
            voter_id,
            booth_id,
            slot_id,
            operation_type,
            lock_acquired_at,
            lock_released_at,
            status_code,
            execution_latency_ms,
            details,
            created_at
        FROM os_concurrency_audit
        ORDER BY audit_id DESC
        LIMIT %s;
        """
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            for r in rows:
                if r.get("created_at"):
                    r["created_at"] = str(r["created_at"])
                if r.get("lock_acquired_at"):
                    r["lock_acquired_at"] = str(r["lock_acquired_at"])
                if r.get("lock_released_at"):
                    r["lock_released_at"] = str(r["lock_released_at"])
                if r.get("execution_latency_ms") is not None:
                    r["execution_latency_ms"] = float(r["execution_latency_ms"])
            return rows

    def get_system_telemetry(self) -> Dict[str, Any]:
        """Consolidates OS Scheduler, Synchronization, and LRU Cache metrics."""
        return {
            "scheduler": os_scheduler.get_metrics(),
            "synchronization": sync_manager.get_metrics(),
            "lru_cache": os_lru_cache.get_stats(),
            "recent_file_traces": os_file_logger.get_recent_logs(n=10)
        }

# Singleton instance
allocation_service = AllocationService()
