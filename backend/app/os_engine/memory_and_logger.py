"""
OS Memory Management & Rotating File System Audit Logger
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Demonstrates:
  1. Memory Management: Bounded In-Memory Least-Recently-Used (LRU) Page/Object Cache with TTL.
  2. File Management: Structured Rotating File Logging (JSONL traces) for OS Transactions.
"""

import os
import sys
import json
import time
import threading
import logging
from collections import OrderedDict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple

# -----------------------------------------------------------------------------
# 1. OS MEMORY MANAGEMENT: Bounded Least-Recently-Used (LRU) Cache
# -----------------------------------------------------------------------------
class BoundedLRUCache:
    """
    Thread-safe bounded Least-Recently-Used (LRU) in-memory cache.
    Simulates OS Virtual Memory Page Replacement (LRU policy) with Time-To-Live (TTL).
    """
    def __init__(self, max_pages: int = 128, ttl_seconds: Optional[float] = None):
        self.max_pages = max_pages
        self.ttl_seconds = ttl_seconds or float(os.getenv("BOOTH_CACHE_TTL_SECONDS", "300"))
        
        # OrderedDict maintains key insertion/access order
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()
        
        # Memory metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.page_evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieves an item from cache, refreshing its LRU position if not expired."""
        with self._lock:
            if key not in self._cache:
                self.cache_misses += 1
                return None

            value, timestamp = self._cache[key]
            # Check TTL expiry
            if (time.time() - timestamp) > self.ttl_seconds:
                del self._cache[key]
                self.cache_misses += 1
                return None

            # Mark as most recently used
            self._cache.move_to_end(key, last=True)
            self.cache_hits += 1
            return value

    def put(self, key: str, value: Any) -> None:
        """Inserts or updates an item. Evicts the least recently used item if max capacity is exceeded."""
        with self._lock:
            now = time.time()
            if key in self._cache:
                self._cache[key] = (value, now)
                self._cache.move_to_end(key, last=True)
                return

            # Check capacity; evict LRU item (first in OrderedDict)
            if len(self._cache) >= self.max_pages:
                self._cache.popitem(last=False)
                self.page_evictions += 1

            self._cache[key] = (value, now)

    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidates a single key or clears the entire cache."""
        with self._lock:
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Returns real-time memory management metrics."""
        with self._lock:
            current_entries = len(self._cache)
            # Estimate memory footprint
            approx_bytes = sys.getsizeof(self._cache) + sum(
                sys.getsizeof(k) + sys.getsizeof(v[0]) for k, v in self._cache.items()
            )
            hit_ratio = 0.0
            total_lookups = self.cache_hits + self.cache_misses
            if total_lookups > 0:
                hit_ratio = round((self.cache_hits / total_lookups) * 100.0, 2)

            return {
                "max_pages": self.max_pages,
                "current_pages": current_entries,
                "ttl_seconds": self.ttl_seconds,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "hit_ratio_pct": hit_ratio,
                "page_evictions": self.page_evictions,
                "approx_memory_bytes": approx_bytes
            }

# -----------------------------------------------------------------------------
# 2. OS FILE MANAGEMENT: Thread-Safe Rotating File Logger (JSONL)
# -----------------------------------------------------------------------------
class BufferedAuditFileLogger:
    """
    High-performance, thread-safe structured audit logger writing to rotating disk files.
    Emits single-line JSON (JSONL) entries for PCB lifecycles, concurrency locks, and errors.
    """
    def __init__(self, log_dir: Optional[str] = None, max_bytes: int = 5 * 1024 * 1024, backup_count: int = 3):
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        self.log_dir = Path(log_dir) if log_dir else (root_dir / "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "os_concurrency.log"

        self.logger_name = f"os_concurrency_file_logger_{abs(hash(str(self.log_file)))}"
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # Configure rotating file handler if not already attached
        if not self.logger.handlers:
            self.handler = RotatingFileHandler(
                filename=str(self.log_file),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8"
            )
            formatter = logging.Formatter("%(message)s")
            self.handler.setFormatter(formatter)
            self.logger.addHandler(self.handler)
        else:
            self.handler = self.logger.handlers[0]

    def log_trace(
        self,
        event_type: str,
        pcb_dict: Optional[Dict[str, Any]] = None,
        message: str = "",
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """Writes a structured JSON trace line to os_concurrency.log."""
        record = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "timestamp_ms": round(time.time() * 1000.0, 2),
            "thread_id": threading.get_ident(),
            "event_type": event_type,
            "message": message,
            "pcb": pcb_dict,
            "extra": extra or {}
        }
        self.logger.info(json.dumps(record))
        if hasattr(self, "handler") and self.handler:
            self.handler.flush()

    def get_recent_logs(self, n: int = 50) -> List[Dict[str, Any]]:
        """Reads up to n recent JSON records from the log file for API dashboard inspection."""
        if not self.log_file.exists():
            return []
        lines = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        try:
                            lines.append(json.loads(stripped))
                        except json.JSONDecodeError:
                            continue
            return lines[-n:]
        except Exception:
            return []

# Global singletons
os_lru_cache = BoundedLRUCache(max_pages=256)
os_file_logger = BufferedAuditFileLogger()
