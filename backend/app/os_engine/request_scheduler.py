"""
CPU Scheduling & Priority Aging Engine
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Demonstrates: OS CPU Scheduling Algorithms:
              1. First-Come-First-Served (FCFS)
              2. Shortest Job First (SJF)
              3. Priority Scheduling with Aging (Prevents General Voter Starvation)
              4. Round Robin (RR) with Configurable Time Quantum

CONSTITUTIONAL & LEGAL GUARDRAIL:
Software request scheduling prioritizes server-side API queue processing and assistive slot
matching only; it never alters constitutional voter eligibility or legal voting order.
"""

import os
import time
import copy
import threading
import logging
from typing import List, Optional, Dict, Any, Tuple
from backend.app.os_engine.process_lifecycle import RequestPCB, ProcessState
from database.db_pool import db_pool

logger = logging.getLogger("os_scheduler")

class RequestScheduler:
    """
    Thread-safe OS Request Dispatcher supporting FCFS, SJF, Priority Scheduling with Aging,
    and Round Robin with configurable time quantum.
    """
    DISCLAIMER: str = (
        "Software request scheduling prioritizes server-side API queue processing "
        "and assistive slot matching only; it never alters constitutional voter "
        "eligibility or legal voting order."
    )

    SUPPORTED_POLICIES = ("FCFS", "SJF", "PRIORITY_AGING", "ROUND_ROBIN")

    def __init__(
        self,
        policy: Optional[str] = None,
        aging_quantum_ms: float = 10000.0,
        round_robin_quantum_ms: float = 20.0
    ):
        """
        :param policy: 'FCFS', 'SJF', 'PRIORITY_AGING', or 'ROUND_ROBIN'.
        :param aging_quantum_ms: Milliseconds of wait required to decrement effective priority by 0.1.
        :param round_robin_quantum_ms: Execution slice in milliseconds for Round Robin scheduling.
        """
        raw_pol = policy or os.getenv("OS_SCHEDULER_POLICY", "PRIORITY_AGING").upper()
        self.policy = raw_pol if raw_pol in self.SUPPORTED_POLICIES else "PRIORITY_AGING"
        self.aging_quantum_ms = aging_quantum_ms
        self.round_robin_quantum_ms = round_robin_quantum_ms
        self._queue: List[RequestPCB] = []
        self._lock = threading.Lock()
        self._total_dispatched = 0
        self._total_aging_promotions = 0

    def set_policy(self, new_policy: str, round_robin_quantum_ms: Optional[float] = None) -> None:
        """Dynamically reconfigures the scheduling policy and quantum at runtime."""
        with self._lock:
            cleaned = new_policy.upper()
            if cleaned not in self.SUPPORTED_POLICIES:
                raise ValueError(
                    f"Unsupported scheduling policy: {new_policy}. "
                    f"Must be one of {self.SUPPORTED_POLICIES}"
                )
            self.policy = cleaned
            if round_robin_quantum_ms and round_robin_quantum_ms > 0:
                self.round_robin_quantum_ms = float(round_robin_quantum_ms)
            logger.info("Scheduler policy switched to: %s (Quantum: %.1fms)", self.policy, self.round_robin_quantum_ms)

    def enqueue(self, pcb: RequestPCB) -> None:
        """Places a PCB into the Ready Queue and transitions its state to READY."""
        with self._lock:
            pcb.transition_to(ProcessState.READY, f"Enqueued under policy {self.policy}")
            self._queue.append(pcb)

    def apply_aging(self) -> int:
        """
        Iterates over the READY queue and applies the Priority Aging formula:
            effective_priority = base_priority - (wait_time_ms / aging_quantum_ms) * 0.1
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
                self.apply_aging()
                # Lowest effective priority first; tie-break on created_at_ms (FCFS)
                self._queue.sort(key=lambda p: (p.effective_priority, p.created_at_ms))
                winner = self._queue.pop(0)

            elif self.policy == "SJF":
                # Shortest Job First: shortest remaining burst time first
                self._queue.sort(key=lambda p: (p.remaining_burst_time_ms, p.created_at_ms))
                winner = self._queue.pop(0)

            elif self.policy == "ROUND_ROBIN":
                # Round Robin: pop first from queue; simulate time slice
                winner = self._queue.pop(0)
                slice_time = min(self.round_robin_quantum_ms, winner.remaining_burst_time_ms)
                winner.remaining_burst_time_ms -= slice_time
                if winner.remaining_burst_time_ms > 0:
                    # Not yet finished; re-append to ready queue after slice
                    self._queue.append(winner)

            else:  # FCFS mode
                self._queue.sort(key=lambda p: p.created_at_ms)
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
                "supported_policies": list(self.SUPPORTED_POLICIES),
                "aging_quantum_ms": self.aging_quantum_ms,
                "round_robin_quantum_ms": self.round_robin_quantum_ms,
                "current_queue_depth": len(self._queue),
                "total_dispatched": self._total_dispatched,
                "total_aging_promotions": self._total_aging_promotions,
                "disclaimer": self.DISCLAIMER
            }

    # -------------------------------------------------------------------------
    # MULTI-ALGORITHM BENCHMARK & COMPARISON ENGINE
    # -------------------------------------------------------------------------
    @classmethod
    def get_default_benchmark_workload(cls) -> List[Dict[str, Any]]:
        """
        Returns a standardized workload mixing all 4 voter priority tiers
        with realistic burst execution benchmarks for fair algorithm comparison.
        """
        return [
            {
                "task_id": "TASK-P1-01",
                "name": "Sunita Devi (Pregnant Woman Priority)",
                "category": "PREGNANT_WOMEN",
                "priority_level": 1,
                "base_priority": 1.0,
                "arrival_time": 0.0,
                "burst_time": 30.0
            },
            {
                "task_id": "TASK-P2-01",
                "name": "Arvind Singh Negi (PwD Assistive Booking)",
                "category": "PERSON_WITH_DISABILITY",
                "priority_level": 2,
                "base_priority": 2.0,
                "arrival_time": 5.0,
                "burst_time": 20.0
            },
            {
                "task_id": "TASK-P3-01",
                "name": "Ramesh Chandra Sharma (Senior Citizen Fast-Track)",
                "category": "SENIOR_CITIZEN",
                "priority_level": 3,
                "base_priority": 3.0,
                "arrival_time": 10.0,
                "burst_time": 25.0
            },
            {
                "task_id": "TASK-P4-01",
                "name": "Manmohan Singh Bisht (General Early Arrival)",
                "category": "GENERAL",
                "priority_level": 4,
                "base_priority": 4.0,
                "arrival_time": 15.0,
                "burst_time": 45.0
            },
            {
                "task_id": "TASK-P4-02",
                "name": "Pooja Bhatt (General Quick Slot Verification)",
                "category": "GENERAL",
                "priority_level": 4,
                "base_priority": 4.0,
                "arrival_time": 20.0,
                "burst_time": 15.0
            },
            {
                "task_id": "TASK-P4-03",
                "name": "Vikram Pant (General Standard Booking)",
                "category": "GENERAL",
                "priority_level": 4,
                "base_priority": 4.0,
                "arrival_time": 25.0,
                "burst_time": 35.0
            }
        ]

    def simulate_workload(
        self,
        tasks: Optional[List[Dict[str, Any]]] = None,
        policy: str = "FCFS",
        quantum_ms: float = 20.0
    ) -> Dict[str, Any]:
        """
        Simulates execution of a set of tasks under a specified CPU scheduling algorithm.
        Calculates:
          - Arrival Time, Burst Time, Completion Time
          - Waiting Time = Turnaround Time - Burst Time
          - Turnaround Time = Completion Time - Arrival Time
          - Response Time = First Start Time - Arrival Time
          - Average Waiting Time & Average Turnaround Time
          - Gantt Timeline Execution Slices
        """
        pol = policy.upper()
        if pol not in self.SUPPORTED_POLICIES:
            pol = "FCFS"

        workload = copy.deepcopy(tasks or self.get_default_benchmark_workload())
        n = len(workload)
        if n == 0:
            return {"tasks": [], "timeline": [], "metrics": {}}

        # Internal tracking state per task
        task_state: Dict[str, Dict[str, Any]] = {}
        for t in workload:
            tid = t["task_id"]
            name = t.get("name") or t.get("voter_name") or f"Task-{tid}"
            arr = float(t.get("arrival_time") if t.get("arrival_time") is not None else t.get("arrival_time_ms", 0.0))
            burst = float(t.get("burst_time") if t.get("burst_time") is not None else t.get("burst_time_ms", 20.0))
            base_p = float(t.get("base_priority") if t.get("base_priority") is not None else t.get("priority_level", 4.0))
            task_state[tid] = {
                "task_id": tid,
                "name": name,
                "voter_name": name,
                "category": t.get("category", "GENERAL"),
                "priority_level": t.get("priority_level", 4),
                "voter_priority_level": t.get("priority_level", 4),
                "base_priority": base_p,
                "effective_priority": base_p,
                "arrival_time": arr,
                "arrival_time_ms": arr,
                "burst_time": burst,
                "burst_time_ms": burst,
                "remaining_burst": burst,
                "start_time": None,
                "completion_time": 0.0,
                "completion_time_ms": 0.0,
                "waiting_time": 0.0,
                "waiting_time_ms": 0.0,
                "turnaround_time": 0.0,
                "turnaround_time_ms": 0.0,
                "response_time": None,
                "response_time_ms": None
            }

        timeline: List[Dict[str, Any]] = []
        current_time = 0.0
        completed_count = 0

        # Sort initial workload arrival
        all_tids = sorted(task_state.keys(), key=lambda x: task_state[x]["arrival_time"])
        min_arrival = task_state[all_tids[0]]["arrival_time"]
        if current_time < min_arrival:
            current_time = min_arrival

        # ---------------------------------------------------------------------
        # 1. ROUND ROBIN SIMULATION
        # ---------------------------------------------------------------------
        if pol == "ROUND_ROBIN":
            q_ms = max(5.0, float(quantum_ms))
            ready_queue: List[str] = []
            visited = set()

            def add_arrived_tasks(curr_t: float):
                for tid in all_tids:
                    if tid not in visited and task_state[tid]["arrival_time"] <= curr_t:
                        ready_queue.append(tid)
                        visited.add(tid)

            add_arrived_tasks(current_time)

            while completed_count < n:
                if not ready_queue:
                    # CPU idle; jump to next arriving task
                    remaining_unvisited = [tid for tid in all_tids if tid not in visited]
                    if remaining_unvisited:
                        next_arr = min(task_state[tid]["arrival_time"] for tid in remaining_unvisited)
                        current_time = max(current_time, next_arr)
                        add_arrived_tasks(current_time)
                    else:
                        break

                curr_tid = ready_queue.pop(0)
                t_info = task_state[curr_tid]

                if t_info["response_time"] is None:
                    t_info["response_time"] = round(current_time - t_info["arrival_time"], 2)
                    t_info["start_time"] = round(current_time, 2)

                exec_duration = min(q_ms, t_info["remaining_burst"])
                slice_start = current_time
                slice_end = current_time + exec_duration
                current_time = slice_end
                t_info["remaining_burst"] -= exec_duration

                timeline.append({
                    "task_id": curr_tid,
                    "name": t_info["name"],
                    "category": t_info["category"],
                    "start_time": round(slice_start, 2),
                    "end_time": round(slice_end, 2),
                    "duration": round(exec_duration, 2)
                })

                # Check newly arrived tasks during this execution slice
                add_arrived_tasks(current_time)

                if t_info["remaining_burst"] <= 0.001:
                    comp_t = round(current_time, 2)
                    ta_t = round(comp_t - t_info["arrival_time"], 2)
                    wait_t = round(ta_t - t_info["burst_time"], 2)
                    t_info["completion_time"] = comp_t
                    t_info["completion_time_ms"] = comp_t
                    t_info["turnaround_time"] = ta_t
                    t_info["turnaround_time_ms"] = ta_t
                    t_info["waiting_time"] = wait_t
                    t_info["waiting_time_ms"] = wait_t
                    completed_count += 1
                else:
                    ready_queue.append(curr_tid)

        # ---------------------------------------------------------------------
        # 2. NON-PREEMPTIVE POLICIES: FCFS, SJF, PRIORITY_AGING
        # ---------------------------------------------------------------------
        else:
            remaining_tids = list(all_tids)

            while remaining_tids:
                # Find available ready tasks (arrived by current_time)
                ready_tids = [tid for tid in remaining_tids if task_state[tid]["arrival_time"] <= current_time]

                if not ready_tids:
                    # CPU Idle jump
                    current_time = min(task_state[tid]["arrival_time"] for tid in remaining_tids)
                    ready_tids = [tid for tid in remaining_tids if task_state[tid]["arrival_time"] <= current_time]

                # Select winner according to policy
                if pol == "SJF":
                    # Shortest burst time; tie break arrival time
                    ready_tids.sort(key=lambda tid: (task_state[tid]["burst_time"], task_state[tid]["arrival_time"]))
                    winner_tid = ready_tids[0]

                elif pol == "PRIORITY_AGING":
                    # Apply dynamic priority aging to all waiting tasks
                    for tid in ready_tids:
                        wait = current_time - task_state[tid]["arrival_time"]
                        # Aging: Every 10ms of wait drops effective priority by 0.1 (elevating it)
                        age_reduction = (wait / 10.0) * 0.1
                        task_state[tid]["effective_priority"] = max(0.5, task_state[tid]["base_priority"] - age_reduction)

                    # Lowest numerical value = Highest Priority
                    ready_tids.sort(key=lambda tid: (task_state[tid]["effective_priority"], task_state[tid]["arrival_time"]))
                    winner_tid = ready_tids[0]

                else:  # FCFS
                    ready_tids.sort(key=lambda tid: task_state[tid]["arrival_time"])
                    winner_tid = ready_tids[0]

                remaining_tids.remove(winner_tid)
                w_info = task_state[winner_tid]

                start_t = current_time
                end_t = current_time + w_info["burst_time"]
                current_time = end_t

                w_info["start_time"] = round(start_t, 2)
                w_info["completion_time"] = round(end_t, 2)
                w_info["completion_time_ms"] = round(end_t, 2)
                w_info["turnaround_time"] = round(end_t - w_info["arrival_time"], 2)
                w_info["turnaround_time_ms"] = round(end_t - w_info["arrival_time"], 2)
                w_info["waiting_time"] = round(w_info["turnaround_time"] - w_info["burst_time"], 2)
                w_info["waiting_time_ms"] = round(w_info["turnaround_time"] - w_info["burst_time"], 2)
                w_info["response_time"] = round(start_t - w_info["arrival_time"], 2)
                w_info["response_time_ms"] = round(start_t - w_info["arrival_time"], 2)

                timeline.append({
                    "task_id": winner_tid,
                    "name": w_info["name"],
                    "category": w_info["category"],
                    "start_time": round(start_t, 2),
                    "end_time": round(end_t, 2),
                    "duration": round(w_info["burst_time"], 2)
                })

        # Calculate Averages & Telemetry Metrics
        task_list = [task_state[tid] for tid in all_tids]
        avg_waiting = round(sum(t["waiting_time"] for t in task_list) / n, 2)
        avg_turnaround = round(sum(t["turnaround_time"] for t in task_list) / n, 2)
        avg_response = round(sum(t["response_time"] for t in task_list) / n, 2)
        total_time = round(current_time, 2)

        policy_notes = {
            "FCFS": "Standard arrival queue. Susceptible to the Convoy Effect if a long task arrives first.",
            "SJF": "Minimizes average waiting time by executing shortest burst tasks first. Can cause starvation for long tasks under sustained high load.",
            "PRIORITY_AGING": "Prioritizes assistive voter categories (Pregnant Women P1, PwD P2) while applying aging reductions to prevent general voter starvation.",
            "ROUND_ROBIN": f"Time-sliced preemptive rotation (Quantum = {quantum_ms:.0f}ms). Ensures bounded interactive response times and fair CPU sharing."
        }

        return {
            "policy": pol,
            "quantum_ms": quantum_ms if pol == "ROUND_ROBIN" else None,
            "tasks": task_list,
            "timeline": timeline,
            "metrics": {
                "total_tasks": n,
                "total_execution_time_ms": total_time,
                "average_waiting_time_ms": avg_waiting,
                "average_turnaround_time_ms": avg_turnaround,
                "average_response_time_ms": avg_response
            },
            "policy_characteristics": policy_notes.get(pol, ""),
            "disclaimer": self.DISCLAIMER
        }

    def compare_all_algorithms(
        self,
        tasks: Optional[List[Dict[str, Any]]] = None,
        quantum_ms: float = 20.0
    ) -> Dict[str, Any]:
        """
        Executes all 4 scheduling algorithms on an identical task workload.
        Returns side-by-side comparative metrics for academic demonstration.
        """
        workload = tasks or self.get_default_benchmark_workload()
        results: Dict[str, Any] = {}

        for pol in self.SUPPORTED_POLICIES:
            results[pol] = self.simulate_workload(workload, policy=pol, quantum_ms=quantum_ms)

        # Identify optimums
        min_wait_pol = min(self.SUPPORTED_POLICIES, key=lambda p: results[p]["metrics"]["average_waiting_time_ms"])
        min_turnaround_pol = min(self.SUPPORTED_POLICIES, key=lambda p: results[p]["metrics"]["average_turnaround_time_ms"])

        return {
            "workload": workload,
            "algorithms": results,
            "summary_comparison": {
                p: {
                    "average_waiting_time_ms": results[p]["metrics"]["average_waiting_time_ms"],
                    "average_turnaround_time_ms": results[p]["metrics"]["average_turnaround_time_ms"],
                    "average_response_time_ms": results[p]["metrics"]["average_response_time_ms"],
                    "total_time_ms": results[p]["metrics"]["total_execution_time_ms"]
                }
                for p in self.SUPPORTED_POLICIES
            },
            "optimum_for_waiting_time": min_wait_pol,
            "optimum_for_turnaround_time": min_turnaround_pol,
            "academic_insight": (
                "SJF typically yields the lowest average waiting time, while Priority with Aging "
                "protects assistive categories without general voter starvation. "
                "Round Robin maximizes responsiveness for interactive workloads."
            )
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
