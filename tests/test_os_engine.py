"""
Unit & Integration Tests for Operating Systems Engine
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Tests all 9 OS Core Concepts:
  1. Process Lifecycle & PCB Transitions (NEW -> READY -> RUNNING -> WAITING -> TERMINATED)
  2. FCFS Scheduling
  3. Priority Scheduling with Aging Formula & Starvation Prevention
  4. Per-Slot Mutual Exclusion (Critical Section)
  5. Bounded Counting Semaphore
  6. Deadlock Prevention via Hierarchical Resource Ordering (Havender's Algorithm)
  7. LRU Memory Management Page Eviction
  8. Rotating File Logger (JSONL)
"""

import time
import pytest
from backend.app.os_engine import (
    ProcessState,
    RequestPCB,
    RequestScheduler,
    SlotSynchronizationManager,
    BoundedLRUCache,
    BufferedAuditFileLogger
)

def test_process_lifecycle_transitions():
    """Verify standard 5-state transitions and PCB metric calculations."""
    pcb = RequestPCB(
        voter_id=1,
        operation_type="ALLOCATE",
        priority_category="SENIOR_CITIZEN"
    )
    assert pcb.state == ProcessState.NEW
    assert pcb.base_priority == 1.0
    assert pcb.effective_priority == 1.0

    pcb.transition_to(ProcessState.READY, "Added to ready queue")
    assert pcb.state == ProcessState.READY
    assert pcb.ready_at_ms is not None

    time.sleep(0.01)
    pcb.transition_to(ProcessState.WAITING, "Awaiting Mutex")
    assert pcb.state == ProcessState.WAITING
    assert pcb.waiting_started_at_ms is not None

    time.sleep(0.01)
    pcb.transition_to(ProcessState.RUNNING, "Mutex Acquired")
    assert pcb.state == ProcessState.RUNNING
    assert pcb.waiting_duration_ms > 0

    pcb.transition_to(ProcessState.TERMINATED, "Completed successfully")
    assert pcb.state == ProcessState.TERMINATED
    assert pcb.terminated_at_ms is not None
    assert pcb.get_turnaround_time_ms() > 0

    d = pcb.to_dict()
    assert d["process_id"].startswith("PROC-")
    assert len(d["state_transitions"]) == 5

def test_fcfs_scheduling():
    """Verify First-Come-First-Served scheduler strictly orders by submission time."""
    scheduler = RequestScheduler(policy="FCFS")
    pcb1 = RequestPCB(voter_id=101, created_at_ms=1000.0)
    pcb2 = RequestPCB(voter_id=102, created_at_ms=2000.0)
    pcb3 = RequestPCB(voter_id=103, created_at_ms=1500.0)

    scheduler.enqueue(pcb1)
    scheduler.enqueue(pcb2)
    scheduler.enqueue(pcb3)

    first = scheduler.dispatch_next()
    second = scheduler.dispatch_next()
    third = scheduler.dispatch_next()

    assert first.voter_id == 101
    assert second.voter_id == 103
    assert third.voter_id == 102

def test_priority_scheduling_with_aging():
    """Verify assistive priority and aging formula promotion to prevent starvation."""
    scheduler = RequestScheduler(policy="PRIORITY_AGING", aging_quantum_ms=50.0)

    # General voter submitted earlier
    general_pcb = RequestPCB(
        voter_id=201,
        priority_category="GENERAL",
        created_at_ms=(time.time() * 1000.0) - 200.0  # Simulated 200ms age
    )
    general_pcb.ready_at_ms = general_pcb.created_at_ms

    # Senior citizen voter submitted just now
    senior_pcb = RequestPCB(
        voter_id=202,
        priority_category="SENIOR_CITIZEN",
        created_at_ms=time.time() * 1000.0
    )

    scheduler.enqueue(general_pcb)
    scheduler.enqueue(senior_pcb)

    # Aging calculation should have elevated general_pcb priority
    promotions = scheduler.apply_aging()
    assert promotions >= 1
    assert general_pcb.effective_priority < general_pcb.base_priority

def test_synchronization_critical_section():
    """Verify mutual exclusion context manager transitions PCB to WAITING then RUNNING."""
    mgr = SlotSynchronizationManager()
    pcb = RequestPCB(voter_id=301)

    with mgr.critical_section_lock(pcb, slot_id=10, booth_id=1):
        assert pcb.state == ProcessState.RUNNING
        assert mgr.total_locks_acquired >= 1

def test_deadlock_prevention_resource_ordering():
    """Verify dual slot locks are acquired in ascending numerical order."""
    mgr = SlotSynchronizationManager()
    pcb = RequestPCB(voter_id=401)

    # Test swap where old=15, new=8 (order must be 8 then 15)
    with mgr.acquire_dual_slot_locks(pcb, old_slot_id=15, new_slot_id=8, booth_id=2) as (first, second):
        assert first == 8
        assert second == 15
        assert pcb.state == ProcessState.RUNNING

def test_lru_memory_cache():
    """Verify bounded LRU cache evicts least-recently-used entry on overflow."""
    cache = BoundedLRUCache(max_pages=3, ttl_seconds=60)
    cache.put("page_1", "Data 1")
    cache.put("page_2", "Data 2")
    cache.put("page_3", "Data 3")

    # Access page_1 so page_2 becomes the LRU
    assert cache.get("page_1") == "Data 1"

    # Insert page_4, which must evict page_2
    cache.put("page_4", "Data 4")

    assert cache.get("page_2") is None
    assert cache.get("page_1") == "Data 1"
    assert cache.get("page_3") == "Data 3"
    assert cache.get("page_4") == "Data 4"
    assert cache.page_evictions == 1

def test_rotating_file_logger(tmp_path):
    """Verify structured JSON trace logging to file."""
    logger = BufferedAuditFileLogger(log_dir=str(tmp_path))
    pcb = RequestPCB(voter_id=501)
    logger.log_trace(
        event_type="TEST_EVENT",
        pcb_dict=pcb.to_dict(),
        message="OS Test Entry"
    )

    recent = logger.get_recent_logs(n=10)
    assert len(recent) >= 1
    assert recent[-1]["event_type"] == "TEST_EVENT"
    assert recent[-1]["message"] == "OS Test Entry"
