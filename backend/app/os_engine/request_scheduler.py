"""
CPU Scheduling & Priority Aging Engine
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Demonstrates: OS CPU Scheduling Algorithms:
              1. First-Come-First-Served (FCFS)
              2. Priority Scheduling with Aging (prevents starvation of general voter requests)

CONSTITUTIONAL & LEGAL GUARDRAIL:
Software request scheduling prioritizes server-side API queue processing and assistive slot
matching only; it never alters constitutional voter eligibility or legal voting order.
"""

import os
import time
import threading
import logging
from typing import List, Optional, Dict, Any
from backend.app.os_engine.process_lifecycle import RequestPCB, ProcessState
from database.db_pool import db_pool

logger = logging.getLogger("os_scheduler")

class RequestScheduler:
    """
    Thread-safe OS Request Dispatcher supporting FCFS and Priority Scheduling with Aging.
    """
    DISCLAIMER: str = (
        "Software request scheduling prioritizes server-side API queue processing "
        "and assistive slot matching only; it never alters constitutional voter "
        "eligibility or legal voting order."
    )

    def __init__(self, policy: Optional[str] = None, aging_quantum_ms: float = 10000.0):
        """
        :param policy: 'FCFS' or 'PRIORITY_AGING'. Defaults to env OS_SCHEDULER_POLICY or PRIORITY_AGING.
        :param aging_quantum_ms: Milliseconds of wait required to decrement effective priority by 0.1.
        """
        self.policy = policy or os.getenv("OS_SCHEDULER_POLICY", "PRIORITY_AGING").upper()
        self.aging_quantum_ms = aging_quantum_ms
        self._queue: List[RequestPCB] = []
        self._lock = threading.Lock()
        self._total_dispatched = 0
        self._total_aging_promotions = 0

    def set_policy(self, new_policy: str) -> None:
        """Dynamically reconfigures the scheduling policy at runtime."""
        with self._lock:
            cleaned = new_policy.upper()
            if cleaned not in ("FCFS", "PRIORITY_AGING"):
                raise ValueError(f"Unsupported scheduling policy: {new_policy}")
            self.policy = cleaned
            logger.info("Scheduler policy switched to: %s", self.policy)

    def enqueue(self, pcb: RequestPCB) -> None:
        """
        Places a PCB into the Ready Queue and transitions its state to READY.
        """
        with self._lock:
            pcb.transition_to(ProcessState.READY, f"Enqueued under policy {self.policy}")
            self._queue.append(pcb)

    def apply_aging(self) -> int:
        """
        Iterates over the READY queue and applies the Priority Aging formula:
            effective_priority = base_priority - (wait_time_ms / aging_quantum_ms)
        Lower numerical value represents higher dispatch priority.
        Prevents starvation of GENERAL requests waiting behind assistive requests.
        """
        now = time.time() * 1000.0
        promotions = 0

        for pcb in self._queue:
            if pcb.state != ProcessState.READY:
                continue

            wait_time_ms = now - (pcb.ready_at_ms or pcb.created_at_ms)
            age_reduction = (wait_time_ms / self.aging_quantum_ms) * 0.1
            old_priority = pcb.effective_priority
            # Clamp effective priority between 0.5 (highest elevated) and base_priority
            new_priority = max(0.5, pcb.base_priority - age_reduction)

            if new_priority < old_priority:
                pcb.effective_priority = new_priority
                promotions += 1
                self._total_aging_promotions += 1

                # Log promotion event if significant (e.g. general priority crossed 1.5)
                if old_priority >= 1.5 and new_priority < 1.5:
                    self._log_audit_event(
                        pcb=pcb,
                        operation="PRIORITY_ELEVATION",
                        status="AGING_TRIGGERED",
                        latency_ms=wait_time_ms,
                        details=(
                            f"Voter {pcb.voter_id} aged from {old_priority:.2f} "
                            f"to {new_priority:.2f} (wait: {wait_time_ms:.1f}ms)"
                        )
                    )

        return promotions

    def dispatch_next(self) -> Optional[RequestPCB]:
        """
        Selects and dispatches the next PCB according to the configured policy.
        Transitions the selected PCB from READY to RUNNING.
        """
        with self._lock:
            if not self._queue:
                return None

            if self.policy == "PRIORITY_AGING":
                # Apply aging across waiting requests before picking the winner
                self.apply_aging()
                # Sort by effective_priority ascending (lowest number = highest priority),
                # tie-break with created_at_ms (FCFS for identical priorities)
                self._queue.sort(key=lambda p: (p.effective_priority, p.created_at_ms))
            else:
                # FCFS mode: Sort strictly by creation time
                self._queue.sort(key=lambda p: p.created_at_ms)

            # Pop the highest priority / oldest process
            winner = self._queue.pop(0)
            now = time.time() * 1000.0
            dispatch_latency_ms = now - (winner.ready_at_ms or winner.created_at_ms)
            
            winner.transition_to(
                ProcessState.RUNNING,
                f"Dispatched via {self.policy} (Latency: {dispatch_latency_ms:.2f}ms)"
            )
            self._total_dispatched += 1

            return winner

    def get_queue_snapshot(self) -> List[Dict[str, Any]]:
        """Returns a non-blocking snapshot of requests currently waiting in the Ready Queue."""
        with self._lock:
            if self.policy == "PRIORITY_AGING":
                self.apply_aging()
            return [pcb.to_dict() for pcb in self._queue]

    def get_metrics(self) -> Dict[str, Any]:
        """Returns runtime scheduler telemetry."""
        with self._lock:
            return {
                "policy": self.policy,
                "aging_quantum_ms": self.aging_quantum_ms,
                "current_queue_depth": len(self._queue),
                "total_dispatched": self._total_dispatched,
                "total_aging_promotions": self._total_aging_promotions,
                "disclaimer": self.DISCLAIMER
            }

    def _log_audit_event(
        self,
        pcb: RequestPCB,
        operation: str,
        status: str,
        latency_ms: float,
        details: str
    ) -> None:
        """Asynchronously or safely writes an audit event to os_concurrency_audit table."""
        try:
            with db_pool.get_cursor() as (conn, cursor):
                cursor.callproc(
                    "sp_log_os_concurrency_event",
                    [
                        f"SchedulerThread-{pcb.thread_id}",
                        pcb.voter_id,
                        pcb.resources_requested[0] if len(pcb.resources_requested) > 0 else None,
                        pcb.resources_requested[1] if len(pcb.resources_requested) > 1 else None,
                        operation,
                        status,
                        latency_ms,
                        details
                    ]
                )
                conn.commit()
        except Exception as e:
            logger.debug("Scheduler audit log skipped: %s", e)

# Global singleton scheduler instance
os_scheduler = RequestScheduler()
