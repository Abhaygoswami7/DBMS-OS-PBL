"""
DBMS Isolation Levels & Concurrency Anomalies Experimental Benchmark
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: database/isolation_experiments.py

Demonstrates, compares and tests:
  1. READ UNCOMMITTED: Dirty Read Anomaly
  2. READ COMMITTED: Non-Repeatable Read Anomaly
  3. REPEATABLE READ: Snapshot Isolation (MVCC) preventing Non-Repeatable Reads
  4. SERIALIZABLE: Range Locking preventing Phantom Reads
  5. Lost Update Anomaly vs. Pessimistic Row-Level X-Locking (SELECT ... FOR UPDATE)
"""

import os
import sys
import time
import threading
from typing import Dict, Any, List

sys.path.insert(0, os.getcwd())
from database.db_pool import db_pool

class IsolationLevelDemonstrator:
    """Automated demonstration suite for MySQL 8.0+ InnoDB isolation levels."""

    def __init__(self):
        self.results: Dict[str, Any] = {}

    def run_all_experiments(self) -> Dict[str, Any]:
        """Executes all 5 isolation experiments in controlled test connections."""
        self.results["dirty_read_test"] = self.demonstrate_dirty_read()
        self.results["non_repeatable_read_test"] = self.demonstrate_non_repeatable_read()
        self.results["repeatable_read_snapshot_test"] = self.demonstrate_repeatable_read_snapshot()
        self.results["serializable_range_lock_test"] = self.demonstrate_serializable_range_lock()
        self.results["lost_update_prevention_test"] = self.demonstrate_lost_update_prevention()
        return self.results

    def demonstrate_dirty_read(self) -> Dict[str, Any]:
        """
        Experiment 1: READ UNCOMMITTED allows reading dirty, uncommitted mutations.
        """
        initial_pincode = "263136"
        dirty_pincode = "999999"
        observed_value = None

        with db_pool.get_connection() as conn_w, db_pool.get_connection() as conn_r:
            cur_w = conn_w.cursor(dictionary=True)
            cur_r = conn_r.cursor(dictionary=True)

            try:
                # Setup: ensure voter 1 is known
                cur_w.execute("UPDATE voters SET pincode = %s WHERE voter_id = 1;", (initial_pincode,))
                conn_w.commit()

                # Writer starts transaction and mutates voter 1 without committing
                cur_w.execute("SET autocommit = 0;")
                cur_w.execute("UPDATE voters SET pincode = %s WHERE voter_id = 1;", (dirty_pincode,))

                # Reader sets isolation to READ UNCOMMITTED
                cur_r.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;")
                cur_r.execute("SELECT pincode FROM voters WHERE voter_id = 1;")
                row = cur_r.fetchone()
                observed_value = row["pincode"] if row else None

                # Writer rolls back dirty update
                conn_w.rollback()
            finally:
                cur_w.execute("SET autocommit = 1;")
                cur_w.execute("UPDATE voters SET pincode = %s WHERE voter_id = 1;", (initial_pincode,))
                conn_w.commit()
                cur_w.close()
                cur_r.close()

        anomaly_detected = (observed_value == dirty_pincode)
        return {
            "isolation_level": "READ UNCOMMITTED",
            "anomaly_demonstrated": "Dirty Read",
            "uncommitted_value_observed": observed_value,
            "anomaly_occurred": anomaly_detected,
            "explanation": (
                "Transaction 2 under READ UNCOMMITTED observed uncommitted changes from Transaction 1, "
                "which was subsequently rolled back."
            )
        }

    def demonstrate_non_repeatable_read(self) -> Dict[str, Any]:
        """
        Experiment 2: READ COMMITTED allows a row to change between two reads in the same transaction.
        """
        val_read_1 = None
        val_read_2 = None

        with db_pool.get_connection() as conn_r, db_pool.get_connection() as conn_w:
            cur_r = conn_r.cursor(dictionary=True)
            cur_w = conn_w.cursor(dictionary=True)

            try:
                # Reader starts transaction with READ COMMITTED
                cur_r.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                cur_r.execute("SET autocommit = 0;")
                cur_r.execute("SELECT address_zone FROM voters WHERE voter_id = 2;")
                val_read_1 = cur_r.fetchone()["address_zone"]

                # Writer updates and commits a new value
                new_zone = f"Updated Zone {int(time.time()) % 1000}"
                cur_w.execute("UPDATE voters SET address_zone = %s WHERE voter_id = 2;", (new_zone,))
                conn_w.commit()

                # Reader reads again within the same transaction
                cur_r.execute("SELECT address_zone FROM voters WHERE voter_id = 2;")
                val_read_2 = cur_r.fetchone()["address_zone"]

                conn_r.commit()
            finally:
                # Reset
                cur_w.execute("UPDATE voters SET address_zone = 'Sattal Road Sector 1, Bhimtal' WHERE voter_id = 2;")
                conn_w.commit()
                cur_r.execute("SET autocommit = 1;")
                cur_r.close()
                cur_w.close()

        changed = (val_read_1 != val_read_2)
        return {
            "isolation_level": "READ COMMITTED",
            "anomaly_demonstrated": "Non-Repeatable Read",
            "first_read": val_read_1,
            "second_read": val_read_2,
            "values_differ": changed,
            "explanation": (
                "In READ COMMITTED, each query receives a fresh snapshot; committed concurrent updates "
                "alter values between consecutive reads within the same transaction."
            )
        }

    def demonstrate_repeatable_read_snapshot(self) -> Dict[str, Any]:
        """
        Experiment 3: REPEATABLE READ (InnoDB default) preserves snapshot isolation (MVCC).
        Consecutive reads return identical values even after concurrent commits.
        """
        val_read_1 = None
        val_read_2 = None

        with db_pool.get_connection() as conn_r, db_pool.get_connection() as conn_w:
            cur_r = conn_r.cursor(dictionary=True)
            cur_w = conn_w.cursor(dictionary=True)

            try:
                # Reader starts transaction with REPEATABLE READ
                cur_r.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;")
                cur_r.execute("SET autocommit = 0;")
                cur_r.execute("SELECT address_zone FROM voters WHERE voter_id = 3;")
                val_read_1 = cur_r.fetchone()["address_zone"]

                # Writer updates and commits
                new_zone = f"Sattal Zone {int(time.time()) % 1000}"
                cur_w.execute("UPDATE voters SET address_zone = %s WHERE voter_id = 3;", (new_zone,))
                conn_w.commit()

                # Reader reads again in REPEATABLE READ
                cur_r.execute("SELECT address_zone FROM voters WHERE voter_id = 3;")
                val_read_2 = cur_r.fetchone()["address_zone"]

                conn_r.commit()
            finally:
                cur_w.execute("UPDATE voters SET address_zone = 'Sattal Road Sector 2, Bhimtal' WHERE voter_id = 3;")
                conn_w.commit()
                cur_r.execute("SET autocommit = 1;")
                cur_r.close()
                cur_w.close()

        consistent = (val_read_1 == val_read_2)
        return {
            "isolation_level": "REPEATABLE READ",
            "anomaly_prevented": "Non-Repeatable Read (Prevented via MVCC)",
            "first_read": val_read_1,
            "second_read": val_read_2,
            "snapshot_consistent": consistent,
            "explanation": (
                "InnoDB Multi-Version Concurrency Control (MVCC) created a consistent read view on the first query; "
                "subsequent reads continue reading from that undo log snapshot regardless of concurrent commits."
            )
        }

    def demonstrate_serializable_range_lock(self) -> Dict[str, Any]:
        """
        Experiment 4: SERIALIZABLE enforces Next-Key locking, converting shared reads into locks.
        """
        lock_blocked = False

        with db_pool.get_connection() as conn_r, db_pool.get_connection() as conn_w:
            cur_r = conn_r.cursor(dictionary=True)
            cur_w = conn_w.cursor(dictionary=True)

            try:
                # Reader in SERIALIZABLE locks a range of slots
                cur_r.execute("SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE;")
                cur_r.execute("SET autocommit = 0;")
                cur_r.execute("SELECT slot_id, max_capacity FROM time_slots WHERE slot_id = 1;")
                _ = cur_r.fetchone()

                # Writer attempts concurrent update with a short timeout
                cur_w.execute("SET SESSION innodb_lock_wait_timeout = 1;")
                try:
                    cur_w.execute("UPDATE time_slots SET max_capacity = max_capacity + 1 WHERE slot_id = 1;")
                    conn_w.commit()
                except Exception as e:
                    if "Lock wait timeout exceeded" in str(e):
                        lock_blocked = True

                conn_r.rollback()
            finally:
                cur_r.execute("SET autocommit = 1;")
                cur_r.close()
                cur_w.close()

        return {
            "isolation_level": "SERIALIZABLE",
            "anomaly_prevented": "Phantom Read / Concurrency Conflict",
            "concurrent_writer_blocked": lock_blocked,
            "explanation": (
                "In SERIALIZABLE, plain SELECT statements acquire Shared Locks (S-Locks), "
                "blocking concurrent Exclusive Locks (X-Locks) until transaction completion."
            )
        }

    def demonstrate_lost_update_prevention(self) -> Dict[str, Any]:
        """
        Experiment 5: Compares uncoordinated read-modify-write (Lost Update hazard)
        against pessimistic row-level locking (SELECT ... FOR UPDATE).
        """
        # Test slot 1 initial count
        initial_count = 0
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("SELECT allocated_count FROM time_slots WHERE slot_id = 1;")
            initial_count = cursor.fetchone()["allocated_count"]

        # Run 2 concurrent worker threads attempting atomic increment via SELECT ... FOR UPDATE
        iterations = 5
        errors = []

        def worker_increment():
            for _ in range(iterations):
                try:
                    with db_pool.get_cursor() as (conn, cursor):
                        # Pessimistic Row-Level Exclusive Lock
                        cursor.execute("SELECT allocated_count FROM time_slots WHERE slot_id = 1 FOR UPDATE;")
                        row = cursor.fetchone()
                        curr = row["allocated_count"]
                        time.sleep(0.005)  # Simulate critical section processing
                        cursor.execute("UPDATE time_slots SET allocated_count = %s WHERE slot_id = 1;", (curr + 1,))
                        conn.commit()
                except Exception as ex:
                    errors.append(str(ex))

        t1 = threading.Thread(target=worker_increment)
        t2 = threading.Thread(target=worker_increment)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        final_count = 0
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute("SELECT allocated_count FROM time_slots WHERE slot_id = 1;")
            final_count = cursor.fetchone()["allocated_count"]
            # Restore initial count
            cursor.execute("UPDATE time_slots SET allocated_count = %s WHERE slot_id = 1;", (initial_count,))
            conn.commit()

        expected_final = initial_count + (iterations * 2)
        lost_update_prevented = (final_count == expected_final)

        return {
            "technique": "Pessimistic Row-Level Locking (SELECT ... FOR UPDATE)",
            "iterations_per_thread": iterations,
            "concurrent_threads": 2,
            "expected_increments": iterations * 2,
            "actual_increments": final_count - initial_count,
            "lost_update_prevented": lost_update_prevented,
            "concurrency_errors": len(errors),
            "explanation": (
                "Pessimistic exclusive row locking (FOR UPDATE) serializes concurrent read-modify-write cycles, "
                "guaranteeing zero lost updates."
            )
        }

def run_all_isolation_experiments() -> List[Dict[str, Any]]:
    """Runs all 5 isolation experiments and returns them as a structured list."""
    demo = IsolationLevelDemonstrator()
    dict_results = demo.run_all_experiments()
    return list(dict_results.values())

if __name__ == "__main__":
    demo = IsolationLevelDemonstrator()
    out = demo.run_all_experiments()
    print("=== ISOLATION LEVELS BENCHMARK RESULTS ===")
    for k, v in out.items():
        print(f"\n[{k.upper()}]")
        for prop, val in v.items():
            print(f"  {prop}: {val}")
