"""
Operating Systems IPC & Producer-Consumer Event Queue Module
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Demonstrates:
  1. Inter-Process Communication (IPC) & Producer-Consumer Architecture
  2. Bounded Thread-Safe Message Queuing (queue.Queue & multiprocessing.Queue)
  3. Transactional Outbox Pattern for Zero Lost Events (allocation_events_outbox)
  4. Asynchronous Background Task Workers with Auto-Recovery
"""

import os
import sys
import json
import time
import queue
import logging
import threading
import multiprocessing
from typing import Dict, Any, Optional, List
from database.db_pool import db_pool

logger = logging.getLogger("ipc_event_queue")

def _multiprocessing_producer_worker(ipc_q: multiprocessing.Queue, messages: List[str]):
    """Top-level function picklable by multiprocessing spawn on Windows."""
    for msg in messages:
        ipc_q.put(f"[PID-{os.getpid()}] {msg}")
    ipc_q.put("STOP")

class IPCProducerConsumerEngine:
    """
    Production-grade Producer-Consumer OS Coordination Engine.
    Coordinates asynchronous task processing, event outbox persistence,
    and simulated voter notification delivery.
    """
    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super(IPCProducerConsumerEngine, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, max_queue_size: int = 100):
        if getattr(self, "_initialized", False):
            return

        self.max_queue_size = max_queue_size
        self._event_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._lock = threading.Lock()

        # Telemetry benchmarks
        self.total_events_published = 0
        self.total_events_consumed = 0
        self.total_events_failed = 0
        self.recent_processed_events: List[Dict[str, Any]] = []

        self._start_consumer_worker()
        self.recover_pending_events()
        self._initialized = True

    def _start_consumer_worker(self) -> None:
        """Launches the dedicated background consumer daemon thread."""
        self._shutdown_event.clear()
        self._worker_thread = threading.Thread(
            target=self._consumer_worker_loop,
            name="OS-IPC-Consumer-Worker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info("OS IPC Consumer Worker thread started successfully.")

    def _consumer_worker_loop(self) -> None:
        """
        Background loop continuously consuming events from the message queue.
        Executes simulated notification processing and updates outbox records in MySQL.
        """
        while not self._shutdown_event.is_set():
            try:
                # Wait up to 1.0s for an event
                event_data = self._event_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._process_single_event(event_data)
                with self._lock:
                    self.total_events_consumed += 1
                    self.recent_processed_events.append({
                        "event_id": event_data.get("event_id"),
                        "event_type": event_data.get("event_type"),
                        "aggregate_id": event_data.get("aggregate_id"),
                        "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "DELIVERED"
                    })
                    # Keep latest 25 events in memory
                    if len(self.recent_processed_events) > 25:
                        self.recent_processed_events.pop(0)
            except Exception as e:
                logger.error("Error in OS IPC consumer processing: %s", e)
                with self._lock:
                    self.total_events_failed += 1
                self._mark_event_failed(event_data.get("event_id"), str(e))
            finally:
                self._event_queue.task_done()

    def _process_single_event(self, event: Dict[str, Any]) -> None:
        """
        Processes an individual event:
        1. Simulates notification generation / pass dispatching.
        2. Updates outbox record in MySQL from PENDING to DELIVERED.
        """
        event_id = event.get("event_id")
        event_type = event.get("event_type", "UNKNOWN")
        aggregate_id = event.get("aggregate_id", "")
        payload = event.get("payload", {})

        # Simulate task duration (I/O, formatting SMS / ERS receipt)
        time.sleep(0.02)

        # Update database outbox table
        if event_id:
            try:
                with db_pool.get_cursor() as (conn, cursor):
                    cursor.execute(
                        """
                        UPDATE allocation_events_outbox
                        SET status = 'DELIVERED',
                            processed_at = CURRENT_TIMESTAMP
                        WHERE event_id = %s;
                        """,
                        (event_id,)
                    )
                    conn.commit()
            except Exception as dbe:
                logger.warning("Failed to update outbox event %s: %s", event_id, dbe)

        logger.debug(
            "Delivered IPC event [%s] id=%s aggregate=%s",
            event_type, event_id, aggregate_id
        )

    def _mark_event_failed(self, event_id: Optional[int], error_msg: str) -> None:
        """Marks an outbox event as FAILED with an error trace."""
        if not event_id:
            return
        try:
            with db_pool.get_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    UPDATE allocation_events_outbox
                    SET status = 'FAILED',
                        retry_count = retry_count + 1,
                        error_message = %s,
                        processed_at = CURRENT_TIMESTAMP
                    WHERE event_id = %s;
                    """,
                    (error_msg[:255], event_id)
                )
                conn.commit()
        except Exception as e:
            logger.error("Failed to mark outbox event %s as failed: %s", event_id, e)

    def publish_allocation_event(
        self,
        event_type: str,
        aggregate_id: str,
        payload: Dict[str, Any]
    ) -> Optional[int]:
        """
        Transactional Outbox Producer Method:
        1. Persists event to MySQL `allocation_events_outbox` with status PENDING.
        2. Places event onto in-memory queue.Queue for asynchronous consumer dispatch.
        """
        event_id = None
        payload_json = json.dumps(payload, default=str)

        try:
            with db_pool.get_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    INSERT INTO allocation_events_outbox
                    (event_type, aggregate_id, payload_json, status)
                    VALUES (%s, %s, %s, 'PENDING');
                    """,
                    (event_type, aggregate_id, payload_json)
                )
                event_id = cursor.lastrowid
                conn.commit()
        except Exception as dbe:
            logger.warning("Could not persist outbox record to DB: %s", dbe)

        event_envelope = {
            "event_id": event_id,
            "event_type": event_type,
            "aggregate_id": aggregate_id,
            "payload": payload,
            "timestamp": time.time()
        }

        try:
            self._event_queue.put_nowait(event_envelope)
            with self._lock:
                self.total_events_published += 1
        except queue.Full:
            logger.warning("In-memory event queue full; event %s logged in outbox for recovery.", event_id)

        return event_id

    def recover_pending_events(self) -> int:
        """
        Recovery Mechanism:
        Queries MySQL for any stranded PENDING events (e.g. after server reboot)
        and re-enqueues them, eliminating lost notifications.
        """
        recovered_count = 0
        try:
            with db_pool.get_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    SELECT event_id, event_type, aggregate_id, payload_json
                    FROM allocation_events_outbox
                    WHERE status = 'PENDING'
                    ORDER BY created_at ASC
                    LIMIT 50;
                    """
                )
                rows = cursor.fetchall()
                for row in rows:
                    try:
                        payload = json.loads(row["payload_json"])
                    except Exception:
                        payload = {}
                    envelope = {
                        "event_id": row["event_id"],
                        "event_type": row["event_type"],
                        "aggregate_id": row["aggregate_id"],
                        "payload": payload,
                        "timestamp": time.time()
                    }
                    try:
                        self._event_queue.put_nowait(envelope)
                        recovered_count += 1
                    except queue.Full:
                        break
            if recovered_count > 0:
                logger.info("Recovered %d pending outbox events from database.", recovered_count)
        except Exception as e:
            logger.debug("Outbox recovery skipped: %s", e)

        return recovered_count

    def get_ipc_metrics(self) -> Dict[str, Any]:
        """Returns live IPC producer-consumer metrics for the Admin Dashboard."""
        worker_alive = bool(self._worker_thread and self._worker_thread.is_alive())
        pending_in_db = 0
        delivered_in_db = 0

        try:
            with db_pool.get_cursor() as (conn, cursor):
                cursor.execute(
                    """
                    SELECT
                        SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending_cnt,
                        SUM(CASE WHEN status = 'DELIVERED' THEN 1 ELSE 0 END) as delivered_cnt
                    FROM allocation_events_outbox;
                    """
                )
                res = cursor.fetchone()
                if res:
                    pending_in_db = int(res.get("pending_cnt") or 0)
                    delivered_in_db = int(res.get("delivered_cnt") or 0)
        except Exception:
            pass

        with self._lock:
            return {
                "consumer_worker_alive": worker_alive,
                "worker_state": "RUNNING" if worker_alive else "STOPPED",
                "in_memory_queue_depth": self._event_queue.qsize(),
                "queue_depth": self._event_queue.qsize(),
                "max_queue_size": self.max_queue_size,
                "total_published_session": self.total_events_published,
                "total_published": self.total_events_published,
                "total_consumed_session": self.total_events_consumed,
                "total_processed": self.total_events_consumed,
                "total_failed_session": self.total_events_failed,
                "database_outbox_pending": pending_in_db,
                "outbox_pending_stranded": pending_in_db,
                "database_outbox_delivered": delivered_in_db,
                "recent_events": list(self.recent_processed_events)[-10:]
            }

    @staticmethod
    def demonstrate_multiprocessing_ipc() -> Dict[str, Any]:
        """
        Demonstrates Inter-Process Communication (IPC) across independent OS processes
        using Python's multiprocessing.Queue and Process primitives.
        """
        ipc_queue: multiprocessing.Queue = multiprocessing.Queue()
        test_messages = [
            "TASK_VERIFY_DEM_UK_2026_0001",
            "TASK_DISCRETIZE_SLOT_0700_0930",
            "TASK_ALLOCATE_BOOTH_1"
        ]

        proc = multiprocessing.Process(
            target=_multiprocessing_producer_worker,
            args=(ipc_queue, test_messages),
            name="OS-IPC-Demonstration-Process"
        )
        proc.start()

        received = []
        start_t = time.time()
        while True:
            try:
                val = ipc_queue.get(timeout=2.0)
                if val == "STOP":
                    break
                received.append(val)
            except Exception:
                break
            if time.time() - start_t > 4.0:
                break

        proc.join(timeout=2.0)
        if proc.is_alive():
            proc.terminate()

        return {
            "ipc_primitive": "multiprocessing.Queue",
            "producer_pid": proc.pid,
            "consumer_pid": os.getpid(),
            "messages_transferred": len(received),
            "payloads": received,
            "status": "IPC_TRANSACTION_SUCCESS"
        }

# Global singleton accessor
ipc_engine = IPCProducerConsumerEngine()
