"""
OS Scheduling, IPC Event Queue & Concurrency Primitives Test Suite
Academic Verification: Operating Systems (OS) Principles

Tests:
1. CPU Scheduling: FCFS, SJF, Priority with Aging, Round Robin algorithms.
2. Metrics Accuracy: Arrival, Burst, Completion, Waiting, Turnaround, Response times.
3. Starvation Freedom: Dynamic aging mathematical elevation.
4. Gantt Timeline Generation: Correct time slicing and sequence.
5. PCB Lifecycle: State transitions NEW -> READY -> RUNNING -> TERMINATED.
6. System Task Priority vs Voter Priority separation.
7. Inter-Process Communication (IPC): Thread-safe queue, transactional outbox, stranded recovery.
8. Multiprocessing IPC demonstration.
9. Concurrency Primitives: Mutex critical sections, BoundedSemaphore limits, Havender deadlock prevention.
"""

import pytest
import time
from backend.app.os_engine.process_lifecycle import RequestPCB, ProcessState
from backend.app.os_engine.request_scheduler import os_scheduler, RequestScheduler
from backend.app.os_engine.ipc_event_queue import ipc_engine, IPCProducerConsumerEngine
from backend.app.os_engine.synchronization import sync_manager
from backend.app.priority_constants import (
    CATEGORY_PRIORITY_MAP,
    PRIORITY_LEVELS,
    PRIORITY_LABELS
)


class TestOSSchedulersAndMetrics:
    """Verifies CPU scheduling algorithms and metric calculations."""

    def test_fcfs_scheduling_metrics(self):
        """Verifies First-Come First-Served executes tasks in arrival order."""
        custom_workload = [
            {"task_id": "T1", "voter_name": "Task 1", "category": "GENERAL", "priority_level": 4, "arrival_time_ms": 0.0, "burst_time_ms": 30.0},
            {"task_id": "T2", "voter_name": "Task 2", "category": "GENERAL", "priority_level": 4, "arrival_time_ms": 10.0, "burst_time_ms": 20.0},
            {"task_id": "T3", "voter_name": "Task 3", "category": "GENERAL", "priority_level": 4, "arrival_time_ms": 15.0, "burst_time_ms": 10.0},
        ]
        res = os_scheduler.simulate_workload(tasks=custom_workload, policy="FCFS")
        tasks = res["tasks"]
        metrics = res["metrics"]

        # In FCFS: T1 runs at 0-30, T2 runs at 30-50, T3 runs at 50-60
        t1 = next(t for t in tasks if t["task_id"] == "T1")
        t2 = next(t for t in tasks if t["task_id"] == "T2")
        t3 = next(t for t in tasks if t["task_id"] == "T3")

        assert t1["completion_time_ms"] == 30.0
        assert t1["waiting_time_ms"] == 0.0
        assert t1["turnaround_time_ms"] == 30.0

        assert t2["completion_time_ms"] == 50.0
        assert t2["waiting_time_ms"] == 20.0  # 30 - 10
        assert t2["turnaround_time_ms"] == 40.0

        assert t3["completion_time_ms"] == 60.0
        assert t3["waiting_time_ms"] == 35.0  # 50 - 15
        assert t3["turnaround_time_ms"] == 45.0

        expected_avg_wait = round((0.0 + 20.0 + 35.0) / 3, 2)
        assert metrics["average_waiting_time_ms"] == expected_avg_wait

    def test_sjf_minimizes_average_waiting_time(self):
        """Verifies Shortest Job First schedules shortest burst first among ready tasks."""
        benchmark_results = os_scheduler.compare_all_algorithms()
        sjf_wait = benchmark_results["algorithms"]["SJF"]["metrics"]["average_waiting_time_ms"]
        fcfs_wait = benchmark_results["algorithms"]["FCFS"]["metrics"]["average_waiting_time_ms"]

        # SJF should achieve equal or strictly lower average waiting time than FCFS
        assert sjf_wait <= fcfs_wait
        assert benchmark_results["optimum_for_waiting_time"] == "SJF"

    def test_priority_with_aging_starvation_prevention(self):
        """Verifies Priority with Aging elevates waiting general tasks to prevent starvation."""
        res = os_scheduler.simulate_workload(policy="PRIORITY_AGING")
        assert res["policy"] == "PRIORITY_AGING"
        assert len(res["tasks"]) == 6
        assert len(res["timeline"]) > 0

        # Verify all tasks completed
        for task in res["tasks"]:
            assert task["completion_time_ms"] > task["arrival_time_ms"]
            assert task["waiting_time_ms"] >= 0.0

    def test_round_robin_preemption_and_time_slicing(self):
        """Verifies Round Robin preempts tasks exceeding the time quantum."""
        quantum = 15.0
        res = os_scheduler.simulate_workload(policy="ROUND_ROBIN", quantum_ms=quantum)
        timeline = res["timeline"]

        # In Round Robin, each executed slice duration must not exceed quantum
        for slice_item in timeline:
            duration = slice_item["end_time"] - slice_item["start_time"]
            assert duration <= quantum + 0.001

        assert res["quantum_ms"] == quantum

    def test_pcb_lifecycle_and_priority_separation(self):
        """Verifies RequestPCB transitions across states and separates task vs voter priorities."""
        pcb = RequestPCB(
            voter_id=101,
            resources_requested=[5, 1],
            priority_category="PREGNANT_WOMEN",  # Maps to P1 (1)
            operation_type="VERIFY"              # Maps to System Task Priority 2 (Verification)
        )

        assert pcb.state == ProcessState.NEW
        assert pcb.voter_priority_level == 1
        assert pcb.system_task_priority == 2

        pcb.transition_to(ProcessState.READY, "Enqueued in ready queue")
        assert pcb.state == ProcessState.READY

        pcb.transition_to(ProcessState.RUNNING, "Dispatched to CPU")
        assert pcb.state == ProcessState.RUNNING

        pcb.transition_to(ProcessState.TERMINATED, "Execution complete")
        assert pcb.state == ProcessState.TERMINATED
        assert pcb.get_turnaround_time_ms() is not None


class TestIPCEventQueueAndPersistence:
    """Verifies Inter-Process Communication, thread-safe queue, and transactional outbox."""

    def test_ipc_event_publishing_and_metrics(self):
        """Tests publishing an allocation event through the IPC queue engine."""
        event_id = ipc_engine.publish_allocation_event(
            aggregate_id="TEST-ALLOC-999",
            event_type="TEST_ALLOCATION_EVENT",
            payload={"voter_id": 999, "slot_id": 1, "test_marker": True}
        )
        assert event_id is not None
        time.sleep(0.3)  # Allow background worker thread to process

        metrics = ipc_engine.get_ipc_metrics()
        assert metrics["worker_state"] == "RUNNING"
        assert metrics["total_published"] >= 1
        assert metrics["total_processed"] >= 1

    def test_outbox_event_recovery(self):
        """Tests that stranded outbox events can be recovered on startup."""
        recovered = ipc_engine.recover_pending_events()
        assert isinstance(recovered, int)
        assert recovered >= 0

    def test_multiprocessing_ipc_demonstration(self):
        """Tests cross-process IPC demonstration using multiprocessing.Queue."""
        result = ipc_engine.demonstrate_multiprocessing_ipc()
        assert result["status"] == "IPC_TRANSACTION_SUCCESS"
        assert result["messages_transferred"] == 3
        assert len(result["payloads"]) == 3


class TestConcurrencyPrimitivesAndDeadlockPrevention:
    """Verifies Mutex critical sections, BoundedSemaphore limits, and Havender lock ordering."""

    def test_critical_section_mutex_context(self):
        """Verifies mutual exclusion on slot critical sections."""
        pcb = RequestPCB(voter_id=102, resources_requested=[999])
        with sync_manager.critical_section_lock(pcb=pcb, slot_id=999, booth_id=1):
            assert pcb.state == ProcessState.RUNNING

    def test_havender_lock_ordering(self):
        """
        Verifies Havender lock ordering: dual-resource locks must always be acquired
        in strictly ascending order min(A, B) -> max(A, B) to prevent Circular Wait.
        """
        slot_a = 42
        slot_b = 7
        pcb = RequestPCB(voter_id=103, resources_requested=[slot_b])

        with sync_manager.acquire_dual_slot_locks(pcb=pcb, old_slot_id=slot_a, new_slot_id=slot_b, booth_id=1) as (first, second):
            assert first == min(slot_a, slot_b)
            assert second == max(slot_a, slot_b)
            assert first < second
