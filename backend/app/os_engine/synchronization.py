"""
OS Concurrency, Synchronization & Deadlock Prevention Engine
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Demonstrates:
  1. Mutual Exclusion & Critical Sections (Per-Slot Reentrant Mutex Registry)
  2. Counting / Bounded Semaphores (Resource Allocation Limiter for Worker Threads)
  3. Race Condition Elimination (Coordinated application mutex + DB row-level X-locks)
  4. Deadlock Prevention via Resource Hierarchical Ordering (Eliminates Coffman Condition #4: Circular Wait)
"""

import os
import time
import threading
import logging
from contextlib import contextmanager
from typing import Dict, Generator, Tuple, Optional, Any
from backend.app.os_engine.process_lifecycle import RequestPCB, ProcessState
from database.db_pool import db_pool

logger = logging.getLogger("os_synchronization")

class SlotSynchronizationManager:
    """
    Manages process synchronization, fine-grained per-slot critical sections,
    and deadlock-free dual-resource acquisitions.
    """
    def __init__(self):
        max_workers = int(os.getenv("OS_MAX_WORKER_THREADS", "8"))
        self.lock_timeout = float(os.getenv("OS_LOCK_TIMEOUT_SECONDS", "5.0"))
        
        # OS Bounded Semaphore: Limits concurrent active workers accessing critical sections
        self._worker_semaphore = threading.BoundedSemaphore(value=max_workers)
        
        # Registry of fine-grained per-slot recursive locks (RLock)
        self._slot_locks: Dict[int, threading.RLock] = {}
        self._registry_guard = threading.Lock()
        
        # Concurrency telemetry counters
        self.total_locks_acquired = 0
        self.total_lock_timeouts = 0
        self.total_contention_events = 0

    def _get_slot_lock(self, slot_id: int) -> threading.RLock:
        """Retrieves or lazily instantiates an RLock for a given slot_id in a thread-safe manner."""
        with self._registry_guard:
            if slot_id not in self._slot_locks:
                self._slot_locks[slot_id] = threading.RLock()
            return self._slot_locks[slot_id]

    @contextmanager
    def critical_section_lock(
        self,
        pcb: RequestPCB,
        slot_id: int,
        booth_id: int
    ) -> Generator[None, None, None]:
        """
        Critical Section Context Manager:
        1. Acquires worker semaphore slot (Resource Limiting).
        2. Transitions PCB to WAITING while waiting for per-slot Mutex.
        3. Records lock acquisition latency.
        4. Transitions PCB to RUNNING inside the critical section.
        5. Logs acquisition to os_concurrency_audit.
        6. Guarantees safe release on exit.
        """
        slot_lock = self._get_slot_lock(slot_id)
        semaphore_acquired = False
        lock_acquired = False
        start_wait = time.time() * 1000.0

        pcb.resources_requested = [booth_id, slot_id]
        pcb.transition_to(ProcessState.WAITING, f"Waiting for Mutex on slot_id={slot_id}")

        try:
            # Step 1: Acquire Bounded Semaphore
            semaphore_acquired = self._worker_semaphore.acquire(timeout=self.lock_timeout)
            if not semaphore_acquired:
                self.total_lock_timeouts += 1
                self._log_audit_event(
                    pcb=pcb,
                    booth_id=booth_id,
                    slot_id=slot_id,
                    operation="LOCK_TIMEOUT",
                    status="SEMAPHORE_TIMEOUT",
                    latency_ms=time.time() * 1000.0 - start_wait,
                    details=f"Worker semaphore capacity exhausted after {self.lock_timeout}s timeout"
                )
                raise TimeoutError(f"Worker thread pool semaphore exhausted for slot {slot_id}")

            # Step 2: Acquire Per-Slot Mutex Lock
            lock_acquired = slot_lock.acquire(timeout=self.lock_timeout)
            acquire_time = time.time() * 1000.0
            wait_latency_ms = acquire_time - start_wait

            if not lock_acquired:
                self.total_lock_timeouts += 1
                self._log_audit_event(
                    pcb=pcb,
                    booth_id=booth_id,
                    slot_id=slot_id,
                    operation="LOCK_TIMEOUT",
                    status="MUTEX_TIMEOUT",
                    latency_ms=wait_latency_ms,
                    details=f"Per-slot mutex acquisition timed out after {self.lock_timeout}s"
                )
                raise TimeoutError(f"Timeout waiting for mutex lock on slot {slot_id}")

            # Check if contention occurred (wait > 5ms)
            if wait_latency_ms > 5.0:
                self.total_contention_events += 1

            self.total_locks_acquired += 1
            pcb.transition_to(
                ProcessState.RUNNING,
                f"Acquired Mutex on slot_id={slot_id} (Waited: {wait_latency_ms:.2f}ms)"
            )

            self._log_audit_event(
                pcb=pcb,
                booth_id=booth_id,
                slot_id=slot_id,
                operation="SLOT_LOCK",
                status="LOCK_ACQUIRED",
                latency_ms=wait_latency_ms,
                details=f"Mutex lock acquired on time_slots for slot_id={slot_id}"
            )

            # Yield execution control to the critical section payload
            yield

        finally:
            if lock_acquired:
                slot_lock.release()
            if semaphore_acquired:
                self._worker_semaphore.release()

    @contextmanager
    def acquire_dual_slot_locks(
        self,
        pcb: RequestPCB,
        old_slot_id: int,
        new_slot_id: int,
        booth_id: int
    ) -> Generator[Tuple[int, int], None, None]:
        """
        Deadlock Prevention via Resource Hierarchical Ordering (Havender's Algorithm):
        When moving a voter between two slots (old_slot_id <-> new_slot_id),
        strictly acquire locks in ascending numerical order:
            first_slot  = min(old_slot_id, new_slot_id)
            second_slot = max(old_slot_id, new_slot_id)
        
        This mathematically destroys Coffman Condition #4 (Circular Wait),
        preventing deadlocks even when two concurrent threads execute opposite swaps:
          Thread A: Swap 5 -> 12 (acquires 5, then 12)
          Thread B: Swap 12 -> 5 (acquires 5, then 12) -> Thread B safely waits for 5!
        """
        first_slot = min(old_slot_id, new_slot_id)
        second_slot = max(old_slot_id, new_slot_id)

        first_lock = self._get_slot_lock(first_slot)
        second_lock = self._get_slot_lock(second_slot)

        pcb.resources_requested = [booth_id, first_slot, second_slot]
        pcb.transition_to(
            ProcessState.WAITING,
            f"Deadlock-free dual lock ordering: min({first_slot}) -> max({second_slot})"
        )

        first_acquired = False
        second_acquired = False
        start_wait = time.time() * 1000.0

        try:
            # 1. Acquire First Lock (lower numeric ID)
            first_acquired = first_lock.acquire(timeout=self.lock_timeout)
            if not first_acquired:
                raise TimeoutError(f"Deadlock prevention: Failed to acquire primary slot lock {first_slot}")

            # 2. Acquire Second Lock (higher numeric ID)
            second_acquired = second_lock.acquire(timeout=self.lock_timeout)
            if not second_acquired:
                raise TimeoutError(f"Deadlock prevention: Failed to acquire secondary slot lock {second_slot}")

            wait_latency_ms = (time.time() * 1000.0) - start_wait
            pcb.transition_to(
                ProcessState.RUNNING,
                f"Dual locks acquired: [{first_slot}, {second_slot}] (Wait: {wait_latency_ms:.2f}ms)"
            )

            self._log_audit_event(
                pcb=pcb,
                booth_id=booth_id,
                slot_id=first_slot,
                operation="DEADLOCK_RESOLVED",
                status="ORDERED_LOCKS_ACQUIRED",
                latency_ms=wait_latency_ms,
                details=f"Hierarchical resource ordering: acquired {first_slot} then {second_slot}"
            )

            yield (first_slot, second_slot)

        finally:
            # Release in reverse order of acquisition (LIFO unwind)
            if second_acquired:
                second_lock.release()
            if first_acquired:
                first_lock.release()

    def get_metrics(self) -> Dict[str, Any]:
        """Returns runtime synchronization telemetry."""
        with self._registry_guard:
            active_registered_slots = len(self._slot_locks)
        return {
            "registered_slot_locks": active_registered_slots,
            "total_locks_acquired": self.total_locks_acquired,
            "total_lock_timeouts": self.total_lock_timeouts,
            "total_contention_events": self.total_contention_events
        }

    def _log_audit_event(
        self,
        pcb: RequestPCB,
        booth_id: int,
        slot_id: int,
        operation: str,
        status: str,
        latency_ms: float,
        details: str
    ) -> None:
        """Helper to invoke MySQL sp_log_os_concurrency_event."""
        try:
            with db_pool.get_cursor() as (conn, cursor):
                cursor.callproc(
                    "sp_log_os_concurrency_event",
                    [
                        f"WorkerThread-{pcb.thread_id}",
                        pcb.voter_id,
                        booth_id,
                        slot_id,
                        operation,
                        status,
                        latency_ms,
                        details
                    ]
                )
                conn.commit()
        except Exception as e:
            logger.debug("Sync audit log skipped: %s", e)

# Global singleton synchronization manager
sync_manager = SlotSynchronizationManager()
