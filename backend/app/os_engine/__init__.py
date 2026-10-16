"""
OS Engine Package Initializer
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Exports the 9 Core Operating Systems Subsystems:
  1. Process Lifecycle & State Transitions (ProcessState, RequestPCB)
  2. CPU Request Scheduler & Priority Aging (RequestScheduler, os_scheduler)
  3. Mutual Exclusion & Critical Sections (SlotSynchronizationManager, sync_manager)
  4. Counting Semaphores (Bounded Worker Limiter)
  5. Deadlock Prevention via Hierarchical Resource Ordering
  6. Memory Management via Bounded LRU Cache (BoundedLRUCache, os_lru_cache)
  7. File Management via Structured Rotating JSONL Logger (BufferedAuditFileLogger, os_file_logger)
"""

from backend.app.os_engine.process_lifecycle import (
    ProcessState,
    RequestPCB
)

from backend.app.os_engine.request_scheduler import (
    RequestScheduler,
    os_scheduler
)

from backend.app.os_engine.synchronization import (
    SlotSynchronizationManager,
    sync_manager
)

from backend.app.os_engine.memory_and_logger import (
    BoundedLRUCache,
    os_lru_cache,
    BufferedAuditFileLogger,
    os_file_logger
)

__all__ = [
    "ProcessState",
    "RequestPCB",
    "RequestScheduler",
    "os_scheduler",
    "SlotSynchronizationManager",
    "sync_manager",
    "BoundedLRUCache",
    "os_lru_cache",
    "BufferedAuditFileLogger",
    "os_file_logger"
]
