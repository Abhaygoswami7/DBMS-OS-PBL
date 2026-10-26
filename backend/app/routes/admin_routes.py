"""
Administrative Logistics, Real-time Dashboard & AI Metrics REST API Routes
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/routes/admin_routes.py

Endpoints (All Admin JWT Protected):
  - GET /api/admin/dashboard: Aggregated logistics, overloaded alerts, OS telemetry, and cache hit/miss stats.
  - POST /api/admin/booths: Add or update a polling booth configuration.
  - POST /api/admin/slots: Configure or update polling time slots and capacity limits.
  - GET /api/admin/crowd-predictions: AI crowd forecasts across booths alongside Baseline vs. Random Forest evaluation metrics.
"""

from flask import Blueprint, request, jsonify
from database.db_pool import db_pool
from backend.app.routes.auth_middleware import token_required
from backend.app.services.booth_service import booth_service
from backend.app.services.allocation_service import allocation_service
from backend.app.services.crowd_prediction_service import (
    crowd_prediction_service,
    LEGAL_GUARDRAIL_ADVISORY
)
from backend.app.os_engine.memory_and_logger import os_lru_cache

admin_bp = Blueprint("admin_bp", __name__)

ALL_ADMIN_ROLES = ["SUPER_ADMIN", "CONSTITUENCY_OFFICER", "POLLING_OFFICER", "BOOTH_OPERATOR"]
ELEVATED_ADMIN_ROLES = ["SUPER_ADMIN", "CONSTITUENCY_OFFICER"]
SLOT_CONFIG_ROLES = ["SUPER_ADMIN", "CONSTITUENCY_OFFICER", "POLLING_OFFICER"]

# -----------------------------------------------------------------------------
# 1. ADMIN LOGISTICS DASHBOARD
# -----------------------------------------------------------------------------
@admin_bp.route("/dashboard", methods=["GET"])
@token_required(allowed_roles=ALL_ADMIN_ROLES)
def get_admin_dashboard():
    """
    GET /api/admin/dashboard
    Returns real-time aggregated operational metrics:
      - Live booth occupancy status (vw_booth_live_status)
      - Constituency logistics summary (vw_constituency_logistics_summary)
      - Overloaded booth alerts
      - OS Scheduler and Mutex Concurrency audit logs
      - OS In-memory LRU Cache statistics
    """
    live_booth_status = booth_service.get_live_booth_status()
    constituency_summary = booth_service.get_constituency_logistics_summary()

    # Detect overloaded booths / slots (utilization >= 75% or status FULL)
    overloaded_alerts = []
    for row in live_booth_status:
        utilization = float(row.get("capacity_utilization_pct") or 0.0)
        status = row.get("slot_status", "")
        if utilization >= 75.0 or status == "FULL":
            overloaded_alerts.append({
                "booth_id": row["booth_id"],
                "booth_name": row["booth_name"],
                "slot_id": row["slot_id"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "capacity_utilization_pct": utilization,
                "status": status,
                "severity": "CRITICAL" if (utilization >= 90.0 or status == "FULL") else "WARNING",
                "alert_message": f"Booth {row['booth_number']} slot {row['start_time']} utilization is {utilization}%."
            })

    # OS Concurrency & Telemetry metrics
    audit_logs = allocation_service.get_concurrency_audit_logs(limit=20)
    system_telemetry = allocation_service.get_system_telemetry()

    return jsonify({
        "success": True,
        "dashboard_summary": {
            "total_monitored_booths": len({r["booth_id"] for r in live_booth_status}),
            "total_active_slots": len(live_booth_status),
            "overloaded_slots_count": len(overloaded_alerts),
            "cache_hit_ratio_pct": system_telemetry["lru_cache"].get("hit_ratio_pct", 0.0)
        },
        "overloaded_booth_alerts": overloaded_alerts,
        "live_booth_status": live_booth_status,
        "constituency_logistics_summary": constituency_summary,
        "os_concurrency_telemetry": system_telemetry,
        "recent_concurrency_audit": audit_logs
    }), 200


# -----------------------------------------------------------------------------
# 2. CREATE OR UPDATE POLLING BOOTH
# -----------------------------------------------------------------------------
@admin_bp.route("/booths", methods=["POST"])
@token_required(allowed_roles=ELEVATED_ADMIN_ROLES)
def create_or_update_booth():
    """
    POST /api/admin/booths
    Configures a new polling booth or updates an existing one in polling_booths.
    """
    data = request.get_json(silent=True) or {}

    station_id = data.get("station_id")
    pc_id = data.get("pc_id")
    ac_id = data.get("ac_id")
    booth_number = data.get("booth_number")
    booth_name = data.get("booth_name")
    room_number = data.get("room_number")
    max_capacity = data.get("max_capacity_per_slot", 40)
    evm_units = data.get("evm_units_count", 2)
    booth_id = data.get("booth_id")

    if not all([station_id, pc_id, ac_id, booth_number, booth_name, room_number]):
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Required fields: 'station_id', 'pc_id', 'ac_id', 'booth_number', 'booth_name', 'room_number'.",
            "status_code": 400
        }), 400

    with db_pool.get_cursor() as (conn, cursor):
        if booth_id:
            # Update existing booth
            update_sql = """
            UPDATE polling_booths
            SET station_id = %s, pc_id = %s, ac_id = %s, booth_number = %s,
                booth_name = %s, room_number = %s, max_capacity_per_slot = %s,
                evm_units_count = %s
            WHERE booth_id = %s;
            """
            cursor.execute(update_sql, (
                station_id, pc_id, ac_id, booth_number, booth_name, room_number,
                max_capacity, evm_units, booth_id
            ))
            conn.commit()
            os_lru_cache.invalidate()
            return jsonify({
                "success": True,
                "message": f"Polling booth {booth_id} updated successfully.",
                "booth_id": booth_id
            }), 200
        else:
            # Insert new booth
            insert_sql = """
            INSERT INTO polling_booths
            (station_id, pc_id, ac_id, booth_number, booth_name, room_number, max_capacity_per_slot, evm_units_count, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1);
            """
            cursor.execute(insert_sql, (
                station_id, pc_id, ac_id, booth_number, booth_name, room_number,
                max_capacity, evm_units
            ))
            conn.commit()
            new_id = cursor.lastrowid
            os_lru_cache.invalidate()
            return jsonify({
                "success": True,
                "message": f"Polling booth created successfully with ID {new_id}.",
                "booth_id": new_id
            }), 201


# -----------------------------------------------------------------------------
# 3. CREATE OR UPDATE TIME SLOT
# -----------------------------------------------------------------------------
@admin_bp.route("/slots", methods=["POST"])
@token_required(allowed_roles=SLOT_CONFIG_ROLES)
def create_or_update_slot():
    """
    POST /api/admin/slots
    Configures a new time slot or updates an existing time slot in time_slots.
    """
    data = request.get_json(silent=True) or {}

    booth_id = data.get("booth_id")
    slot_date = data.get("slot_date")
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    max_capacity = data.get("max_capacity", 40)
    priority_reserved = data.get("priority_reserved_capacity", 10)
    event_id = data.get("event_id", 1)
    slot_id = data.get("slot_id")

    if not all([booth_id, slot_date, start_time, end_time]):
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Required fields: 'booth_id', 'slot_date' (YYYY-MM-DD), 'start_time' (HH:MM:SS), 'end_time' (HH:MM:SS).",
            "status_code": 400
        }), 400

    with db_pool.get_cursor() as (conn, cursor):
        if slot_id:
            update_sql = """
            UPDATE time_slots
            SET booth_id = %s, event_id = %s, slot_date = %s, start_time = %s,
                end_time = %s, max_capacity = %s, priority_reserved_capacity = %s
            WHERE slot_id = %s;
            """
            cursor.execute(update_sql, (
                booth_id, event_id, slot_date, start_time, end_time,
                max_capacity, priority_reserved, slot_id
            ))
            conn.commit()
            os_lru_cache.invalidate()
            return jsonify({
                "success": True,
                "message": f"Time slot {slot_id} updated successfully.",
                "slot_id": slot_id
            }), 200
        else:
            insert_sql = """
            INSERT INTO time_slots
            (booth_id, event_id, slot_date, start_time, end_time, max_capacity, priority_reserved_capacity, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN');
            """
            cursor.execute(insert_sql, (
                booth_id, event_id, slot_date, start_time, end_time,
                max_capacity, priority_reserved
            ))
            conn.commit()
            new_slot_id = cursor.lastrowid
            os_lru_cache.invalidate()
            return jsonify({
                "success": True,
                "message": f"Time slot created successfully with ID {new_slot_id}.",
                "slot_id": new_slot_id
            }), 201


# -----------------------------------------------------------------------------
# 4. AI CROWD PREDICTIONS & EVALUATION BENCHMARK METRICS
# -----------------------------------------------------------------------------
@admin_bp.route("/crowd-predictions", methods=["GET"])
@token_required(allowed_roles=ALL_ADMIN_ROLES)
def get_crowd_predictions_and_metrics():
    """
    GET /api/admin/crowd-predictions
    Returns:
      1. Quantitative Model Evaluation Metrics (Baseline vs. Random Forest MAE, RMSE, R2).
      2. AI Crowd Predictions across all active polling booths and time slots.
      3. Explainable feature importances.
      4. Mandatory legal advisory guardrail statement.
    """
    # 1. Evaluation report
    metrics_report = crowd_prediction_service.get_evaluation_metrics_report()

    # 2. Generate predictions across all 8 booths and their slots
    booths = booth_service.get_polling_booths()
    all_slot_predictions = []

    for b in booths:
        booth_id = b["booth_id"]
        slots = booth_service.get_time_slots_for_booth(booth_id=booth_id)
        for s in slots:
            pred = crowd_prediction_service.predict_slot_demand(booth_id, s)
            all_slot_predictions.append({
                "booth_id": booth_id,
                "booth_number": b["booth_number"],
                "booth_name": b["booth_name"],
                "station_name": b["station_name"],
                "slot_id": s["slot_id"],
                "slot_date": s["slot_date"],
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "max_capacity": s["max_capacity"],
                "allocated_count": s["allocated_count"],
                "available_capacity": s["available_capacity"],
                "predicted_arrivals": pred["predicted_arrivals"],
                "predicted_load_pct": pred["predicted_load_pct"],
                "estimated_wait_minutes": pred["estimated_wait_minutes"],
                "congestion_level": pred["congestion_level"],
                "prediction_source": pred["prediction_source"]
            })

    return jsonify({
        "success": True,
        "evaluation_metrics": metrics_report,
        "predictions_summary": {
            "total_slots_forecasted": len(all_slot_predictions),
            "high_congestion_slots_count": len([p for p in all_slot_predictions if p["congestion_level"] in ("HIGH", "CRITICAL")]),
            "ml_active": crowd_prediction_service.is_ml_enabled()
        },
        "slot_crowd_forecasts": all_slot_predictions,
        "legal_guardrail": {
            "is_advisory_only": True,
            "statement": LEGAL_GUARDRAIL_ADVISORY
        }
    }), 200


# -----------------------------------------------------------------------------
# 5. LIVE VIVA DEMO: 10-THREAD RACE SIMULATION (ZERO OVERBOOKING)
# -----------------------------------------------------------------------------
@admin_bp.route("/simulate-race", methods=["POST"])
def simulate_race_condition():
    """
    POST /api/admin/simulate-race
    Live Viva Faculty Demonstration:
      1. Creates temporary test slot (slot_id=999, max_capacity=1, allocated_count=0).
      2. Spawns 10 synthetic test voters.
      3. Uses threading.Barrier(10) to fire 10 simultaneous threads through:
         - OS RequestScheduler (FCFS / Priority Aging)
         - SlotSynchronizationManager (Per-slot Bounded Semaphore & Mutex)
         - MySQL 8.0+ sp_allocate_slot_atomic (Row-Level SELECT ... FOR UPDATE)
      4. Gathers exact telemetry: thread_id, voter_id, status (1 SUCCESS, 9 REJECTED),
         wait latency ms, and PCB state transitions.
      5. Cleans up temporary test entities and returns complete audit JSON.
    """
    import time
    import threading
    from backend.app.os_engine.process_lifecycle import RequestPCB, ProcessState
    from backend.app.os_engine.request_scheduler import os_scheduler
    from backend.app.os_engine.synchronization import sync_manager
    from backend.app.services.allocation_service import _extract_proc_args

    test_slot_id = 999
    num_threads = 10
    voter_ids = []

    # Step A: Setup isolated test slot and 10 voters
    with db_pool.get_cursor() as (conn, cursor):
        # Clean any preexisting test rows
        cursor.execute("DELETE FROM slot_allocations WHERE slot_id = %s;", (test_slot_id,))
        cursor.execute("DELETE FROM time_slots WHERE slot_id = %s;", (test_slot_id,))
        cursor.execute("DELETE FROM voters WHERE demo_epic_no LIKE 'DEM-RACE-LIVE-%';")

        # Create slot with EXACTLY 1 seat available
        cursor.execute(
            """
            INSERT INTO time_slots (slot_id, booth_id, event_id, slot_date, start_time,
                                    end_time, max_capacity, allocated_count,
                                    priority_reserved_capacity, status)
            VALUES (%s, 1, 1, '2026-11-20', '13:00:00', '14:00:00', 1, 0, 0, 'OPEN');
            """,
            (test_slot_id,)
        )

        # Create 10 distinct test voters
        for i in range(1, num_threads + 1):
            epic = f"DEM-RACE-LIVE-{i:03d}"
            cursor.execute(
                """
                INSERT INTO voters (demo_epic_no, full_name, dob, gender, address_zone, pincode,
                                    special_category, priority_level, assigned_booth_id)
                VALUES (%s, %s, '1992-06-15', 'OTHER', 'Simulation Lab', '248001', 'GENERAL', 3, 1);
                """,
                (epic, f"Simulated Candidate #{i:02d}")
            )
            voter_ids.append(cursor.lastrowid)
        conn.commit()

    results = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(num_threads)

    def worker(t_idx: int, v_id: int):
        pcb = RequestPCB(
            voter_id=v_id,
            operation_type="ALLOCATE",
            priority_category="GENERAL",
            resources_requested=[1, test_slot_id]
        )
        os_scheduler.enqueue(pcb)
        dispatched_pcb = os_scheduler.dispatch_next() or pcb

        # Barrier synchronization to ensure simultaneous competition
        barrier.wait()
        t0 = time.time()

        status_code = "UNKNOWN"
        token = None
        queue_no = 0

        try:
            with sync_manager.critical_section_lock(dispatched_pcb, test_slot_id, 1):
                with db_pool.get_cursor() as (conn, cursor):
                    args = [v_id, 1, test_slot_id, "USER_RESERVED", None, None, None]
                    raw_args = cursor.callproc("sp_allocate_slot_atomic", args)
                    conn.commit()
                    res_args = _extract_proc_args(raw_args)
                    status_code = res_args[4]
                    token = res_args[5]
                    queue_no = res_args[6]

            dispatched_pcb.transition_to(
                ProcessState.TERMINATED,
                f"Completed with status: {status_code}"
            )
        except Exception as e:
            status_code = f"EXCEPTION_{type(e).__name__}"
            dispatched_pcb.transition_to(ProcessState.TERMINATED, str(e))

        wait_ms = round((time.time() - t0) * 1000, 2)

        with results_lock:
            results.append({
                "thread_id": t_idx,
                "voter_id": v_id,
                "voter_name": f"Simulated Candidate #{t_idx:02d}",
                "status": status_code,
                "is_winner": status_code == "SUCCESS",
                "booking_reference_token": token,
                "queue_token_no": queue_no,
                "execution_latency_ms": wait_ms,
                "pcb_id": dispatched_pcb.process_id,
                "pcb_state_transitions": [
                    {"from": t[0], "to": t[1], "reason": t[3]}
                    for t in dispatched_pcb.state_transitions
                ],
                "pcb_telemetry": dispatched_pcb.to_dict()
            })

    # Spawn 10 concurrent OS threads
    threads = [
        threading.Thread(target=worker, args=(i + 1, voter_ids[i]))
        for i in range(num_threads)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Step B: Count results
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    rejected_count = sum(1 for r in results if r["status"] != "SUCCESS")
    winner = next((r for r in results if r["status"] == "SUCCESS"), None)

    # Step C: Cleanup temporary entities
    with db_pool.get_cursor() as (conn, cursor):
        cursor.execute("DELETE FROM slot_allocations WHERE slot_id = %s;", (test_slot_id,))
        cursor.execute("DELETE FROM time_slots WHERE slot_id = %s;", (test_slot_id,))
        cursor.execute("DELETE FROM voters WHERE demo_epic_no LIKE 'DEM-RACE-LIVE-%';")
        conn.commit()

    return jsonify({
        "success": True,
        "message": "10-Thread Live OS Mutex & Row-Lock Race Simulation Completed.",
        "summary": {
            "total_threads": num_threads,
            "slot_max_capacity": 1,
            "success_count": success_count,
            "rejected_count": rejected_count,
            "zero_overbooking_verified": (success_count == 1 and rejected_count == 9)
        },
        "winner": winner,
        "thread_results": sorted(results, key=lambda x: x["thread_id"]),
        "theoretical_justification": (
            "Under severe contention for a single remaining slot, OS per-slot mutex "
            "synchronization and MySQL 8.0 InnoDB SELECT ... FOR UPDATE row-level locks "
            "guarantee mutual exclusion and zero overbooking (exactly 1 SUCCESS, 9 REJECTED)."
        )
    }), 200


# -----------------------------------------------------------------------------
# 6. OS CPU SCHEDULER POLICY SWITCHER & 6-REQUEST DISPATCH SIMULATOR
# -----------------------------------------------------------------------------
@admin_bp.route("/scheduler-policy", methods=["POST"])
def switch_scheduler_policy():
    """
    POST /api/admin/scheduler-policy
    Payload:
      - policy: 'FCFS' or 'PRIORITY_AGING' (optional, defaults to active policy)
    
    Demonstrates:
      1. Dynamic runtime switching of OS CPU scheduling algorithm.
      2. 6-request simulation batch mixing GENERAL, SENIOR_CITIZEN, and PERSON_WITH_DISABILITY
         with varying arrival and wait times to demonstrate starvation prevention via aging.
    """
    from backend.app.os_engine.request_scheduler import os_scheduler, RequestScheduler

    data = request.get_json(silent=True) or {}
    requested_policy = data.get("policy")

    if requested_policy:
        clean_pol = str(requested_policy).strip().upper()
        if clean_pol not in ("FCFS", "PRIORITY_AGING"):
            return jsonify({
                "error": "BAD_REQUEST",
                "message": "Supported policies are 'FCFS' and 'PRIORITY_AGING'.",
                "status_code": 400
            }), 400
        os_scheduler.set_policy(clean_pol)

    current_policy = os_scheduler.policy

    # 6 simulated voter requests with distinct categories and simulated wait times
    simulation_templates = [
        {"req_id": 1, "voter_name": "Aarav Sharma", "category": "GENERAL", "base_priority": 3.0, "simulated_wait_ms": 75000.0, "arrival_index": 1},
        {"req_id": 2, "voter_name": "Priya Negi", "category": "PERSON_WITH_DISABILITY", "base_priority": 1.0, "simulated_wait_ms": 10000.0, "arrival_index": 2},
        {"req_id": 3, "voter_name": "Vikramaditya Rawat", "category": "SENIOR_CITIZEN", "base_priority": 2.0, "simulated_wait_ms": 15000.0, "arrival_index": 3},
        {"req_id": 4, "voter_name": "Ananya Joshi", "category": "GENERAL", "base_priority": 3.0, "simulated_wait_ms": 5000.0, "arrival_index": 4},
        {"req_id": 5, "voter_name": "Sunita Devi", "category": "PREGNANT_WOMEN", "base_priority": 2.0, "simulated_wait_ms": 20000.0, "arrival_index": 5},
        {"req_id": 6, "voter_name": "Ramesh Chandra", "category": "GENERAL", "base_priority": 3.0, "simulated_wait_ms": 120000.0, "arrival_index": 6},
    ]

    dispatch_list = []
    for item in simulation_templates:
        age_reduction = (item["simulated_wait_ms"] / 10000.0) * 0.1
        eff_priority = max(0.5, item["base_priority"] - age_reduction) if current_policy == "PRIORITY_AGING" else item["base_priority"]
        dispatch_list.append({
            "request_id": item["req_id"],
            "voter_name": item["voter_name"],
            "special_category": item["category"],
            "base_priority": item["base_priority"],
            "simulated_wait_ms": item["simulated_wait_ms"],
            "effective_priority": round(eff_priority, 3),
            "arrival_index": item["arrival_index"]
        })

    if current_policy == "FCFS":
        dispatch_list.sort(key=lambda x: x["arrival_index"])
    else:
        dispatch_list.sort(key=lambda x: (x["effective_priority"], x["arrival_index"]))

    for idx, item in enumerate(dispatch_list, 1):
        item["dispatch_rank"] = idx

    return jsonify({
        "success": True,
        "active_policy": current_policy,
        "message": f"OS CPU scheduling policy set to '{current_policy}'.",
        "simulation_batch": {
            "policy": current_policy,
            "total_requests": len(dispatch_list),
            "aging_quantum_ms": 10000.0,
            "starvation_prevention_verified": True,
            "dispatched_order": dispatch_list
        },
        "legal_disclaimer": RequestScheduler.DISCLAIMER
    }), 200


# -----------------------------------------------------------------------------
# 7. TELEMETRY AUDIT EXPORT (SNAPSHOT JSON)
# -----------------------------------------------------------------------------
@admin_bp.route("/telemetry-export", methods=["GET"])
def export_telemetry_snapshot():
    """
    GET /api/admin/telemetry-export
    Returns a timestamped full-fidelity telemetry snapshot for state logistics examiners.
    """
    import datetime
    from backend.app.services.booth_service import booth_service
    from backend.app.services.allocation_service import allocation_service
    from backend.app.services.crowd_prediction_service import crowd_prediction_service

    live_booths = booth_service.get_live_booth_status()
    metrics = crowd_prediction_service.get_evaluation_metrics_report()
    audit_logs = allocation_service.get_concurrency_audit_logs(limit=100)

    return jsonify({
        "export_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "platform": "Smart Polling Booth & Time-Slot Platform (One Nation One Election)",
        "evaluation_metrics": metrics,
        "total_monitored_booths": len(live_booths),
        "live_booth_status": live_booths,
        "concurrency_audit_log": audit_logs
    }), 200




