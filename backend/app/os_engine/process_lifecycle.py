"""
Operating Systems Process Lifecycle & Process Control Block (PCB) Module
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Demonstrates: Process Management, 5-State Process Model (NEW, READY, RUNNING, WAITING, TERMINATED),
              Process Control Block (PCB), Context & Telemetry Tracking.
"""

import time
import uuid
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from backend.app.priority_constants import (
    CATEGORY_BASE_PRIORITY_MAP,
    CATEGORY_PRIORITY_MAP
)

class ProcessState(str, Enum):
    """The 5 Standard OS Process States (Silberschatz, Galvin, Gagne model)."""
    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    TERMINATED = "TERMINATED"

@dataclass
class RequestPCB:
    """
    Process Control Block (PCB) representing an individual transaction or allocation request.
    Stores process identification, priority status, hardware/thread context, and state transitions.
    Distinguishes Voter Service Priority (P1..P4) from OS System Task Priority (Critical, Verification, Background, Reporting).
    """
    task_id: str = field(default_factory=lambda: f"TASK-{uuid.uuid4().hex[:6].upper()}")
    process_id: str = field(default_factory=lambda: f"PROC-{uuid.uuid4().hex[:8].upper()}")
    thread_id: int = field(default_factory=threading.get_ident)
    voter_id: Optional[int] = None
    operation_type: str = "ALLOCATE"  # REGISTER, VERIFY, ALLOCATE, CANCEL, REALLOCATE, REPORT
    priority_category: str = "GENERAL"  # PREGNANT_WOMEN (P1), PERSON_WITH_DISABILITY (P2), SENIOR_CITIZEN (P3), GENERAL (P4)
    voter_priority_level: int = 4  # 1=P1, 2=P2, 3=P3, 4=P4
    system_task_priority: int = 1  # 1=Critical Allocation, 2=Verification, 3=Background AI, 4=Reporting
    base_priority: float = 4.0  # 1.0 (P1), 2.0 (P2), 3.0 (P3), 4.0 (P4)
    effective_priority: float = 4.0
    state: ProcessState = ProcessState.NEW
    
    # Timing & Execution benchmarks in milliseconds
    burst_time_ms: float = 25.0
    remaining_burst_time_ms: float = 25.0
    created_at_ms: float = field(default_factory=lambda: time.time() * 1000.0)
    ready_at_ms: Optional[float] = None
    running_at_ms: Optional[float] = None
    waiting_started_at_ms: Optional[float] = None
    waiting_duration_ms: float = 0.0
    terminated_at_ms: Optional[float] = None
    
    # System resources requested (e.g. slot_id, booth_id)
    resources_requested: List[int] = field(default_factory=list)
    
    # Chronological log of state transitions: (from_state, to_state, timestamp_ms, reason)
    state_transitions: List[Tuple[str, str, float, str]] = field(default_factory=list)

    def __post_init__(self):
        # Set voter service priority & base priority from centralized mapping
        clean_cat = (self.priority_category or "GENERAL").strip().upper()
        self.priority_category = clean_cat
        self.voter_priority_level = CATEGORY_PRIORITY_MAP.get(clean_cat, 4)
        self.base_priority = CATEGORY_BASE_PRIORITY_MAP.get(clean_cat, 4.0)
        self.effective_priority = self.base_priority
        
        # Determine OS System Task Priority based on operation type
        op = (self.operation_type or "ALLOCATE").upper()
        if op in ("ALLOCATE", "REALLOCATE", "CANCEL", "SLOT_RESERVE"):
            self.system_task_priority = 1  # Critical database transaction
            self.burst_time_ms = 35.0
        elif op in ("VERIFY", "SIMULATED_VERIFY", "AUTHENTICATE"):
            self.system_task_priority = 2  # Identity verification task
            self.burst_time_ms = 20.0
        elif op in ("CROWD_PREDICT", "RECOMMEND", "GEO_RANK"):
            self.system_task_priority = 3  # Background computation / prediction
            self.burst_time_ms = 15.0
        else:
            self.system_task_priority = 4  # Reporting, logging, housekeeping
            self.burst_time_ms = 10.0
            
        self.remaining_burst_time_ms = self.burst_time_ms
        
        # Record initial NEW state
        self.state_transitions.append(
            ("NONE", ProcessState.NEW.value, self.created_at_ms, "PCB Initialized")
        )

    def transition_to(self, new_state: ProcessState, reason: str = "") -> None:
        """
        Executes a valid OS process state transition and records metrics.
        """
        now = time.time() * 1000.0
        old_state = self.state

        # Update waiting duration accumulator if transitioning out of WAITING
        if old_state == ProcessState.WAITING and self.waiting_started_at_ms is not None:
            self.waiting_duration_ms += (now - self.waiting_started_at_ms)
            self.waiting_started_at_ms = None

        # State entry hooks
        if new_state == ProcessState.READY:
            if self.ready_at_ms is None:
                self.ready_at_ms = now
        elif new_state == ProcessState.WAITING:
            self.waiting_started_at_ms = now
        elif new_state == ProcessState.RUNNING:
            if self.running_at_ms is None:
                self.running_at_ms = now
            self.thread_id = threading.get_ident()
        elif new_state == ProcessState.TERMINATED:
            self.terminated_at_ms = now

        self.state = new_state
        self.state_transitions.append((old_state.value, new_state.value, now, reason))

    def get_turnaround_time_ms(self) -> float:
        """Turnaround Time = Completion Time - Submission Time."""
        if self.terminated_at_ms:
            return round(self.terminated_at_ms - self.created_at_ms, 3)
        return round((time.time() * 1000.0) - self.created_at_ms, 3)

    def get_response_time_ms(self) -> float:
        """Response Time = First Time in RUNNING state - Submission Time."""
        if self.running_at_ms:
            return round(self.running_at_ms - self.created_at_ms, 3)
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serializes PCB into a dictionary suitable for API responses and audit logs."""
        return {
            "task_id": self.task_id,
            "process_id": self.process_id,
            "thread_id": self.thread_id,
            "voter_id": self.voter_id,
            "operation_type": self.operation_type,
            "priority_category": self.priority_category,
            "voter_priority_level": self.voter_priority_level,
            "system_task_priority": self.system_task_priority,
            "base_priority": self.base_priority,
            "effective_priority": round(self.effective_priority, 4),
            "state": self.state.value,
            "burst_time_ms": round(self.burst_time_ms, 2),
            "remaining_burst_time_ms": round(self.remaining_burst_time_ms, 2),
            "created_at_ms": round(self.created_at_ms, 2),
            "ready_at_ms": round(self.ready_at_ms, 2) if self.ready_at_ms else None,
            "running_at_ms": round(self.running_at_ms, 2) if self.running_at_ms else None,
            "waiting_duration_ms": round(self.waiting_duration_ms, 2),
            "terminated_at_ms": round(self.terminated_at_ms, 2) if self.terminated_at_ms else None,
            "turnaround_time_ms": self.get_turnaround_time_ms(),
            "response_time_ms": self.get_response_time_ms(),
            "resources_requested": self.resources_requested,
            "state_transitions": [
                {
                    "from_state": t[0],
                    "to_state": t[1],
                    "timestamp_ms": round(t[2], 2),
                    "reason": t[3]
                }
                for t in self.state_transitions
            ]
        }
