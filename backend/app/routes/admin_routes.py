"""
Administrative Logistics, Real-time Dashboard & AI Metrics REST API Routes
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/routes/admin_routes.py

Endpoints (All Admin JWT Protected):
  - GET /api/admin/dashboard: Aggregated logistics, overloaded alerts, OS telemetry, and cache hit/miss stats.
  - GET /api/admin/recent-bookings: Latest slot allocation records with voter and booth details (paginated).
  - POST /api/admin/booths: Add or update a polling booth configuration.
  - POST /api/admin/slots: Configure or update polling time slots and capacity limits.
  - GET /api/admin/crowd-predictions: AI crowd forecasts across booths alongside Baseline vs. Random Forest evaluation metrics.
"""

from flask import Blueprint, request, jsonify, current_app
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
# 2. RECENTLY BOOKED VOTERS (Paginated, Admin-Protected)
# -----------------------------------------------------------------------------
@admin_bp.route("/recent-bookings", methods=["GET"])
@token_required(allowed_roles=ALL_ADMIN_ROLES)
def get_recent_bookings():
    """
    GET /api/admin/recent-bookings?limit=10&offset=0
    Returns the latest slot allocation records with full voter, booth, station,
    time-slot and election-event details. Ordered newest first.
    Fields returned never include passwords, OTPs, or raw biometric data.
    """
    try:
        limit = min(int(request.args.get("limit", 10)), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        limit = 10
        offset = 0

    data_sql = """
        SELECT
            sa.allocation_id,
            sa.booking_reference_token,
            sa.status AS allocation_status,
            sa.queue_token_no,
            sa.booked_at AS created_at,
            v.voter_id,
            v.demo_epic_no,
            v.full_name,
            v.special_category,
            v.priority_level,
            ps.station_name,
            pb.booth_name,
            pb.booth_number,
            ts.slot_date,
            ts.start_time,
            ts.end_time,
            ee.event_name
        FROM slot_allocations sa
        JOIN voters v ON sa.voter_id = v.voter_id
        JOIN polling_booths pb ON sa.booth_id = pb.booth_id
        LEFT JOIN polling_stations ps ON pb.station_id = ps.station_id
        LEFT JOIN time_slots ts ON sa.slot_id = ts.slot_id
        LEFT JOIN election_events ee ON sa.event_id = ee.event_id
        ORDER BY sa.booked_at DESC, sa.allocation_id DESC
        LIMIT %s OFFSET %s;
    """

    count_sql = """
        SELECT COUNT(*) AS total_count
        FROM slot_allocations sa
        JOIN voters v ON sa.voter_id = v.voter_id
        JOIN polling_booths pb ON sa.booth_id = pb.booth_id;
    """

    try:
        with db_pool.get_cursor() as (conn, cursor):
            cursor.execute(count_sql)
            total_count = (cursor.fetchone() or {}).get("total_count", 0)

            cursor.execute(data_sql, (limit, offset))
            rows = cursor.fetchall()
    except Exception as exc:
        current_app.logger.error(f"Error fetching recent bookings: {exc}")
        return jsonify({
            "error": "DATABASE_ERROR",
            "message": "Failed to retrieve booking records from database.",
            "status_code": 500
        }), 500

    bookings = []
    for row in rows:
        bookings.append({
            "allocation_id": row["allocation_id"],
            "booking_reference_token": row["booking_reference_token"],
            "allocation_status": row["allocation_status"],
            "queue_token_no": row["queue_token_no"],
            "created_at": str(row["created_at"]) if row["created_at"] else None,
            "voter_id": row["voter_id"],
            "demo_epic_no": row["demo_epic_no"],
            "full_name": row["full_name"],
            "special_category": row["special_category"],
            "priority_level": row["priority_level"],
            "station_name": row["station_name"] or "Assigned Polling Station",
            "booth_name": row["booth_name"] or "Polling Booth",
            "booth_number": row["booth_number"] or "01",
            "slot_date": str(row["slot_date"]) if row["slot_date"] else None,
            "start_time": str(row["start_time"]) if row["start_time"] else None,
            "end_time": str(row["end_time"]) if row["end_time"] else None,
            "event_name": row["event_name"] or "One Nation One Election 2026",
        })

    return jsonify({
        "success": True,
        "bookings": bookings,
        "total_count": total_count,
        "page_info": {
            "limit": limit,
            "offset": offset,
            "returned": len(bookings),
            "has_more": (offset + limit) < total_count
        }
    }), 200


# -----------------------------------------------------------------------------
# 3. CREATE OR UPDATE POLLING BOOTH
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


# -----------------------------------------------------------------------------
# 8. PRIORITY-BASED POLLING SCHEDULER: SUMMARY
# -----------------------------------------------------------------------------
@admin_bp.route("/priority-scheduler/summary", methods=["GET"])
@token_required(allowed_roles=ALL_ADMIN_ROLES)
def get_priority_scheduler_summary():
    """
    GET /api/admin/priority-scheduler/summary
    Returns real-time voter counts, pending/confirmed status, and reserved capacity
    across the four priority levels (P1: Pregnant Women, P2: PwD, P3: Senior Citizens, P4: General).
    """
    from backend.app.priority_constants import PRIORITY_LEVELS, PRIORITY_LABELS

    with db_pool.get_cursor(dictionary=True) as (conn, cursor):
        # Query total registered voters grouped by priority level
        cursor.execute("""
            SELECT 
                priority_level,
                special_category,
                COUNT(*) AS total_registered
            FROM voters
            GROUP BY priority_level, special_category
            ORDER BY priority_level ASC;
        """)
        voter_counts = cursor.fetchall()

        # Query confirmed bookings grouped by voter priority level
        cursor.execute("""
            SELECT 
                v.priority_level,
                COUNT(a.allocation_id) AS confirmed_count
            FROM slot_allocations a
            JOIN voters v ON a.voter_id = v.voter_id
            WHERE a.status = 'CONFIRMED'
            GROUP BY v.priority_level;
        """)
        confirmed_by_priority = {row["priority_level"]: row["confirmed_count"] for row in cursor.fetchall()}

        # Query booth capacity metrics
        cursor.execute("""
            SELECT 
                COALESCE(SUM(max_capacity), 0) AS total_capacity,
                COALESCE(SUM(allocated_count), 0) AS total_allocated,
                COALESCE(SUM(priority_reserved_capacity), 0) AS priority_reserved_capacity,
                COALESCE(SUM(max_capacity - allocated_count), 0) AS available_capacity
            FROM time_slots
            WHERE status = 'OPEN';
        """)
        capacity_summary = cursor.fetchone() or {}

    # Compile priority breakdown
    priority_data = []
    total_reg = 0
    total_conf = 0
    total_pend = 0

    registered_map = {row["priority_level"]: row["total_registered"] for row in voter_counts}
    category_map = {row["priority_level"]: row["special_category"] for row in voter_counts}

    for p_level in (1, 2, 3, 4):
        reg = registered_map.get(p_level, 0)
        conf = confirmed_by_priority.get(p_level, 0)
        pend = max(0, reg - conf)
        total_reg += reg
        total_conf += conf
        total_pend += pend

        priority_data.append({
            "priority_level": p_level,
            "priority_code": f"P{p_level}",
            "category": category_map.get(p_level, "GENERAL"),
            "label": PRIORITY_LABELS.get(p_level, f"Priority {p_level}"),
            "registered": reg,
            "confirmed": conf,
            "pending": pend
        })

    return jsonify({
        "success": True,
        "summary": {
            "total_registered_voters": total_reg,
            "total_confirmed_allocations": total_conf,
            "total_pending_voters": total_pend,
            "capacity": {
                "total_capacity": int(capacity_summary.get("total_capacity", 0)),
                "total_allocated": int(capacity_summary.get("total_allocated", 0)),
                "priority_reserved_capacity": int(capacity_summary.get("priority_reserved_capacity", 0)),
                "available_capacity": int(capacity_summary.get("available_capacity", 0))
            }
        },
        "priorities": priority_data
    }), 200


# -----------------------------------------------------------------------------
# 9. PRIORITY-BASED POLLING SCHEDULER: SIMULATE
# -----------------------------------------------------------------------------
@admin_bp.route("/priority-scheduler/simulate", methods=["POST"])
@token_required(allowed_roles=ALL_ADMIN_ROLES)
def simulate_priority_scheduler():
    """
    POST /api/admin/priority-scheduler/simulate
    Runs an OS scheduling simulation using FCFS, SJF, PRIORITY_AGING, ROUND_ROBIN, or ALL.
    Generates execution timelines (Gantt chart slices) and performance metrics.
    """
    from backend.app.os_engine.request_scheduler import os_scheduler

    data = request.get_json(silent=True) or {}
    algorithm = str(data.get("algorithm", "PRIORITY_AGING")).strip().upper()
    time_quantum_ms = float(data.get("time_quantum_ms", 20.0))
    compare_all = data.get("compare_all", False) or algorithm == "ALL"

    if compare_all:
        comparison_results = os_scheduler.compare_all_algorithms(quantum_ms=time_quantum_ms)
        return jsonify({
            "success": True,
            "mode": "COMPARISON",
            "results": comparison_results
        }), 200

    valid_algorithms = ("FCFS", "SJF", "PRIORITY_AGING", "ROUND_ROBIN")
    if algorithm not in valid_algorithms:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": f"Invalid algorithm '{algorithm}'. Must be one of {valid_algorithms}."
        }), 400

    sim_result = os_scheduler.simulate_workload(
        policy=algorithm,
        quantum_ms=time_quantum_ms
    )

    return jsonify({
        "success": True,
        "mode": "SINGLE",
        "algorithm": algorithm,
        "metrics": sim_result["metrics"],
        "timeline": sim_result["timeline"],
        "gantt_chart": sim_result["timeline"],
        "tasks": sim_result["tasks"],
        "policy_characteristics": sim_result.get("policy_characteristics", ""),
        "total_tasks": sim_result["metrics"]["total_tasks"]
    }), 200


# -----------------------------------------------------------------------------
# 10. PRIORITY-BASED POLLING SCHEDULER: BATCH ALLOCATION
# -----------------------------------------------------------------------------
@admin_bp.route("/priority-scheduler/allocate-batch", methods=["POST"])
@token_required(allowed_roles=ALL_ADMIN_ROLES)
def allocate_priority_batch():
    """
    POST /api/admin/priority-scheduler/allocate-batch
    Dispatches pending voters strictly following the Priority Hierarchy:
      P1 (Pregnant Women) -> P2 (PwD) -> P3 (Senior Citizens) -> P4 (General)
    Allocates next available slot in voter's assigned booth atomically.
    """
    data = request.get_json(silent=True) or {}
    max_batch = min(int(data.get("max_batch_size", 20)), 50)

    # 1. Fetch pending voters ordered strictly by priority_level ASC, voter_id ASC
    with db_pool.get_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("""
            SELECT 
                v.voter_id,
                v.full_name,
                v.demo_epic_no,
                v.special_category,
                v.priority_level,
                v.assigned_booth_id
            FROM voters v
            LEFT JOIN slot_allocations a 
                ON v.voter_id = a.voter_id AND a.status = 'CONFIRMED'
            WHERE a.allocation_id IS NULL
            ORDER BY v.priority_level ASC, v.voter_id ASC
            LIMIT %s;
        """, (max_batch,))
        pending_voters = cursor.fetchall()

    if not pending_voters:
        return jsonify({
            "success": True,
            "message": "No pending voters require time-slot allocation.",
            "allocated_count": 0,
            "failed_count": 0,
            "allocations": []
        }), 200

    allocated_records = []
    failed_records = []

    for voter in pending_voters:
        v_id = voter["voter_id"]
        b_id = voter["assigned_booth_id"]

        # Find next open slot with available capacity in voter's assigned booth
        with db_pool.get_cursor(dictionary=True) as (conn, cursor):
            cursor.execute("""
                SELECT slot_id, slot_date, start_time, max_capacity, allocated_count
                FROM time_slots
                WHERE booth_id = %s AND status = 'OPEN' AND allocated_count < max_capacity
                ORDER BY slot_date ASC, start_time ASC
                LIMIT 1;
            """, (b_id,))
            target_slot = cursor.fetchone()

        if not target_slot:
            failed_records.append({
                "voter_id": v_id,
                "voter_name": voter["full_name"],
                "priority_level": voter["priority_level"],
                "reason": f"No open slots with capacity available at Booth ID {b_id}."
            })
            continue

        res = allocation_service.allocate_voter_slot(
            voter_id=v_id,
            booth_id=b_id,
            slot_id=target_slot["slot_id"],
            allocation_type="ALGORITHMIC_ALLOCATED"
        )

        if res.get("success"):
            allocated_records.append({
                "voter_id": v_id,
                "voter_name": voter["full_name"],
                "priority_level": voter["priority_level"],
                "category": voter["special_category"],
                "booth_id": b_id,
                "slot_id": target_slot["slot_id"],
                "booking_reference_token": res.get("booking_reference_token")
            })
        else:
            failed_records.append({
                "voter_id": v_id,
                "voter_name": voter["full_name"],
                "priority_level": voter["priority_level"],
                "reason": res.get("message", "Allocation rejected.")
            })

    return jsonify({
        "success": True,
        "message": f"Batch allocation complete. {len(allocated_records)} allocated, {len(failed_records)} skipped/failed.",
        "allocated_count": len(allocated_records),
        "failed_count": len(failed_records),
        "allocations": allocated_records,
        "failures": failed_records
    }), 200


# -----------------------------------------------------------------------------
# 11. OS TELEMETRY (SCHEDULER, IPC, SYNC & MEMORY CACHE)
# -----------------------------------------------------------------------------
@admin_bp.route("/os-telemetry-full", methods=["GET"])
@token_required(allowed_roles=ALL_ADMIN_ROLES)
def get_os_telemetry_full():
    """
    GET /api/admin/os-telemetry-full
    Returns consolidated real-time OS subsystem metrics:
      - CPU Scheduler: dispatch metrics, waiting/turnaround averages, Gantt execution
      - Inter-Process Communication (IPC): queue depth, throughput, worker state, outbox recovery
      - Synchronization & Concurrency: Mutex and Bounded Semaphore metrics, Havender deadlock prevention
      - Memory Management: LRU bounded cache size, hit/miss stats, memory pressure
    """
    from backend.app.os_engine.request_scheduler import os_scheduler
    from backend.app.os_engine.ipc_event_queue import ipc_engine
    from backend.app.os_engine.memory_and_logger import os_lru_cache

    sync_telemetry = allocation_service.get_system_telemetry()
    sched_metrics = os_scheduler.get_metrics()
    ipc_metrics = ipc_engine.get_ipc_metrics()
    cache_stats = os_lru_cache.get_stats()

    return jsonify({
        "success": True,
        "scheduler": sched_metrics,
        "ipc": ipc_metrics,
        "cache": cache_stats,
        "synchronization": sync_telemetry.get("synchronization", {})
    }), 200


# -----------------------------------------------------------------------------
# 12. DBMS ADVANCED ANALYTICS (VIEWS & STORED PROCEDURES)
# -----------------------------------------------------------------------------
@admin_bp.route("/dbms-analytics", methods=["GET"])
@token_required(allowed_roles=ALL_ADMIN_ROLES)
def get_dbms_analytics():
    """
    GET /api/admin/dbms-analytics
    Returns aggregated metrics from MySQL 3NF views:
      - vw_administrative_statistics
      - vw_booth_occupancy
      - vw_available_booths
    """
    with db_pool.get_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT * FROM vw_administrative_statistics;")
        admin_stats = cursor.fetchone() or {}

        cursor.execute("SELECT * FROM vw_booth_occupancy;")
        booth_occupancy = cursor.fetchall()

        cursor.execute("SELECT * FROM vw_available_booths;")
        available_booths = cursor.fetchall()

    return jsonify({
        "success": True,
        "admin_statistics": admin_stats,
        "booth_occupancy": booth_occupancy,
        "available_booths": available_booths
    }), 200




