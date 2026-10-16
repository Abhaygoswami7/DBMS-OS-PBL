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
    """
    process_id: str = field(default_factory=lambda: f"PROC-{uuid.uuid4().hex[:8].upper()}")
    thread_id: int = field(default_factory=threading.get_ident)
    voter_id: Optional[int] = None
    operation_type: str = "ALLOCATE"  # REGISTER, VERIFY, ALLOCATE, CANCEL, REALLOCATE
    priority_category: str = "GENERAL"  # SENIOR_CITIZEN, PERSON_WITH_DISABILITY, PREGNANT_WOMEN, GENERAL
    base_priority: float = 2.0  # 1.0 for assistive categories, 2.0 for general
    effective_priority: float = 2.0
    state: ProcessState = ProcessState.NEW
    
    # Timing benchmarks in milliseconds
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
        # Set base priority according to category
        assistive_categories = {"SENIOR_CITIZEN", "PERSON_WITH_DISABILITY", "PREGNANT_WOMEN"}
        if self.priority_category in assistive_categories:
            self.base_priority = 1.0
        else:
            self.base_priority = 2.0
        self.effective_priority = self.base_priority
        
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
            "process_id": self.process_id,
            "thread_id": self.thread_id,
            "voter_id": self.voter_id,
            "operation_type": self.operation_type,
            "priority_category": self.priority_category,
            "base_priority": self.base_priority,
            "effective_priority": round(self.effective_priority, 4),
            "state": self.state.value,
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
