"""
Slot Allocation, Slip Generation & Cancellation REST API Routes
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/routes/allocation_routes.py

Endpoints:
  - POST /api/allocations: Acquire critical section mutex, invoke sp_allocate_slot_atomic, return PCB telemetry.
  - GET /api/allocations/<id>: Retrieve digital appointment pass slip (vw_voter_appointment_slip).
  - DELETE /api/allocations/<id>: Atomically cancel active allocation via sp_cancel_slot_atomic.
"""

from flask import Blueprint, request, jsonify
from database.db_pool import db_pool
from backend.app.services.allocation_service import allocation_service

allocation_bp = Blueprint("allocation_bp", __name__)

@allocation_bp.route("/allocations", methods=["POST"])
def create_allocation():
    """
    POST /api/allocations
    Payload:
      - voter_id: int (required)
      - booth_id: int (required)
      - slot_id: int (required)
      - allocation_type: str (optional, default 'USER_RESERVED')

    Workflow:
      1. Initializes and enqueues OS RequestPCB.
      2. Dispatches PCB to Critical Section per-slot mutex.
      3. Invokes stored procedure sp_allocate_slot_atomic with row-level locks.
      4. Returns 201 on success, 409 on duplicate or full capacity, 400 on bad request.
    """
    data = request.get_json(silent=True) or {}

    voter_id = data.get("voter_id")
    booth_id = data.get("booth_id")
    slot_id = data.get("slot_id")
    allocation_type = data.get("allocation_type", "USER_RESERVED")

    if not voter_id or not booth_id or not slot_id:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Missing required fields: 'voter_id', 'booth_id', 'slot_id'.",
            "status_code": 400
        }), 400

    try:
        v_id = int(voter_id)
        b_id = int(booth_id)
        s_id = int(slot_id)
    except (ValueError, TypeError):
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "'voter_id', 'booth_id', and 'slot_id' must be integers.",
            "status_code": 400
        }), 400

    alloc_res = allocation_service.allocate_voter_slot(
        voter_id=v_id,
        booth_id=b_id,
        slot_id=s_id,
        allocation_type=allocation_type
    )

    if alloc_res["success"]:
        return jsonify({
            "success": True,
            "status": "CONFIRMED",
            "message": "Polling time-slot allocated successfully.",
            "booking_reference_token": alloc_res["booking_reference_token"],
            "queue_number": alloc_res["queue_token_no"],
            "queue_token_no": alloc_res["queue_token_no"],
            "appointment_slip": alloc_res.get("appointment_slip"),
            "pcb_telemetry": alloc_res.get("pcb_telemetry", {})
        }), 201

    status_code = alloc_res.get("status_code", "UNKNOWN_ERROR")

    # Handle 409 Conflict conditions
    if status_code == "DUPLICATE_BOOKING_PREVENTED":
        return jsonify({
            "error": "CONFLICT",
            "status_code": status_code,
            "message": "Voter already possesses an active confirmed booking for this election event.",
            "pcb_telemetry": alloc_res.get("pcb_telemetry", {})
        }), 409

    if status_code in ("SLOT_FULL_CAPACITY_EXCEEDED", "SLOT_CAPACITY_EXCEEDED", "PRIORITY_CAPACITY_EXCEEDED"):
        return jsonify({
            "error": "CONFLICT",
            "status_code": status_code,
            "message": "The requested polling time slot has reached full capacity.",
            "pcb_telemetry": alloc_res.get("pcb_telemetry", {})
        }), 409

    if status_code == "INVALID_BOOTH_JURISDICTION":
        return jsonify({
            "error": "BAD_REQUEST",
            "status_code": status_code,
            "message": "Voter is not registered in this polling booth jurisdiction.",
            "pcb_telemetry": alloc_res.get("pcb_telemetry", {})
        }), 400

    if status_code == "CONCURRENCY_LOCK_TIMEOUT":
        return jsonify({
            "error": "SERVICE_UNAVAILABLE",
            "status_code": status_code,
            "message": "Critical section lock timeout. Slot is under high concurrency contention.",
            "pcb_telemetry": alloc_res.get("pcb_telemetry", {})
        }), 503

    return jsonify({
        "error": status_code,
        "status_code": status_code,
        "message": f"Slot allocation could not be completed: {status_code}",
        "pcb_telemetry": alloc_res.get("pcb_telemetry", {})
    }), 400


@allocation_bp.route("/allocations/<path:alloc_id>", methods=["GET"])
def get_appointment_slip(alloc_id):
    """
    GET /api/allocations/<id>
    Retrieves voter appointment slip (vw_voter_appointment_slip).
    Accepts:
      - Numeric allocation_id (e.g. 1)
      - String booking_reference_token (e.g. TKN-UK-1-1763180400-1001)
    """
    token = None
    numeric_id = None

    if alloc_id.startswith("TKN-") or "-" in alloc_id:
        token = alloc_id
    else:
        try:
            numeric_id = int(alloc_id)
        except ValueError:
            token = alloc_id

    slip = None
    if token:
        slip = allocation_service.get_voter_appointment_slip(booking_reference_token=token)
    elif numeric_id is not None:
        slip = allocation_service.get_voter_appointment_slip(allocation_id=numeric_id)

    if not slip:
        return jsonify({
            "error": "NOT_FOUND",
            "message": f"Appointment slip for allocation identifier '{alloc_id}' not found.",
            "status_code": 404
        }), 404

    return jsonify({
        "success": True,
        "appointment_slip": slip
    }), 200


@allocation_bp.route("/allocations/<path:alloc_id>", methods=["DELETE"])
def cancel_allocation(alloc_id):
    """
    DELETE /api/allocations/<id>
    Cancels an active slot allocation atomically via sp_cancel_slot_atomic.
    Accepts:
      - String booking_reference_token (e.g. TKN-UK-1-1763180400-1001)
      - Numeric allocation_id (e.g. 1)
    Frees slot capacity atomically and updates status to CANCELLED.
    """
    token = alloc_id

    # If numeric allocation_id passed, look up its token
    if not (alloc_id.startswith("TKN-") or "-" in alloc_id):
        try:
            alloc_num = int(alloc_id)
            with db_pool.get_cursor() as (conn, cursor):
                cursor.execute(
                    "SELECT booking_reference_token, status FROM slot_allocations WHERE allocation_id = %s;",
                    (alloc_num,)
                )
                row = cursor.fetchone()
                if not row:
                    return jsonify({
                        "error": "NOT_FOUND",
                        "message": f"Allocation record with ID {alloc_id} not found.",
                        "status_code": 404
                    }), 404
                if row["status"] != "CONFIRMED":
                    return jsonify({
                        "error": "NOT_FOUND",
                        "message": f"Allocation record {alloc_id} is already in state '{row['status']}'.",
                        "status_code": 404
                    }), 404
                token = row["booking_reference_token"]
        except ValueError:
            token = alloc_id

    cancel_res = allocation_service.cancel_slot_allocation(booking_reference_token=token)

    if cancel_res["success"]:
        return jsonify({
            "success": True,
            "status": "CANCELLED",
            "message": f"Slot allocation for booking token '{token}' cancelled successfully. Capacity freed.",
            "booking_reference_token": token,
            "pcb_telemetry": cancel_res.get("pcb_telemetry", {})
        }), 200

    status_code = cancel_res.get("status_code", "CANCELLATION_FAILED")
    if status_code in (
        "ALLOCATION_NOT_FOUND",
        "CANNOT_CANCEL_NON_CONFIRMED",
        "BOOKING_NOT_FOUND_OR_INACTIVE",
        "BOOKING_NOT_FOUND"
    ):
        return jsonify({
            "error": "NOT_FOUND",
            "message": f"Active booking reference '{token}' not found or already cancelled ({status_code}).",
            "status_code": 404
        }), 404

    return jsonify({
        "error": status_code,
        "message": f"Could not cancel allocation: {status_code}",
        "status_code": 400
    }), 400


# -----------------------------------------------------------------------------
# 4. DEADLOCK-SAFE SLOT RESCHEDULING (Coffman Condition Prevention)
# -----------------------------------------------------------------------------
@allocation_bp.route("/allocations/<path:alloc_id>/reschedule", methods=["PUT"])
def reschedule_allocation(alloc_id):
    """
    PUT /api/allocations/<booking_token>/reschedule
    Payload:
      - new_slot_id: int (required)
    
    Guarantees:
      1. Dual resource ordering: min(old_slot_id, new_slot_id) -> max(old_slot_id, new_slot_id).
      2. Atomically frees capacity in old slot and reserves capacity in new slot inside ACID transaction.
      3. Returns updated appointment slip, lock acquisition order, and PCB telemetry.
    """
    data = request.get_json(silent=True) or {}
    new_slot_id = data.get("new_slot_id")

    if not new_slot_id:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Missing required field: 'new_slot_id'.",
            "status_code": 400
        }), 400

    try:
        new_slot_num = int(new_slot_id)
    except (ValueError, TypeError):
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "'new_slot_id' must be an integer.",
            "status_code": 400
        }), 400

    # Retrieve current active allocation
    with db_pool.get_cursor() as (conn, cursor):
        if alloc_id.startswith("TKN-") or "-" in alloc_id:
            cursor.execute(
                """
                SELECT allocation_id, voter_id, booth_id, slot_id, booking_reference_token, status
                FROM slot_allocations
                WHERE booking_reference_token = %s;
                """,
                (alloc_id,)
            )
        else:
            try:
                numeric_id = int(alloc_id)
                cursor.execute(
                    """
                    SELECT allocation_id, voter_id, booth_id, slot_id, booking_reference_token, status
                    FROM slot_allocations
                    WHERE allocation_id = %s;
                    """,
                    (numeric_id,)
                )
            except ValueError:
                cursor.execute(
                    """
                    SELECT allocation_id, voter_id, booth_id, slot_id, booking_reference_token, status
                    FROM slot_allocations
                    WHERE booking_reference_token = %s;
                    """,
                    (alloc_id,)
                )

        row = cursor.fetchone()

    if not row or row["status"] != "CONFIRMED":
        return jsonify({
            "error": "NOT_FOUND",
            "message": f"Active confirmed allocation for '{alloc_id}' not found.",
            "status_code": 404
        }), 404

    voter_id = row["voter_id"]
    booth_id = row["booth_id"]
    old_slot_id = row["slot_id"]
    token = row["booking_reference_token"]

    if int(old_slot_id) == new_slot_num:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "New slot ID must be different from current slot ID.",
            "status_code": 400
        }), 400

    lock_order = [min(int(old_slot_id), new_slot_num), max(int(old_slot_id), new_slot_num)]

    realloc_res = allocation_service.reallocate_voter_slot(
        voter_id=voter_id,
        booth_id=booth_id,
        old_slot_id=int(old_slot_id),
        new_slot_id=new_slot_num,
        booking_reference_token=token
    )

    if realloc_res["success"]:
        new_token = realloc_res["new_booking_reference_token"]
        new_slip = allocation_service.get_voter_appointment_slip(booking_reference_token=new_token)
        return jsonify({
            "success": True,
            "status": "CONFIRMED",
            "message": "Time-slot successfully rescheduled with deadlock-free lock ordering.",
            "booking_reference_token": new_token,
            "new_booking_reference_token": new_token,
            "old_slot_id": int(old_slot_id),
            "new_slot_id": new_slot_num,
            "lock_acquisition_order": lock_order,
            "appointment_slip": new_slip,
            "pcb_telemetry": realloc_res.get("pcb_telemetry", {})
        }), 200

    status_code = realloc_res.get("status_code", "REALLOCATION_FAILED")
    if "CAPACITY" in status_code or "FULL" in status_code:
        return jsonify({
            "error": "CONFLICT",
            "status_code": status_code,
            "message": f"Target time-slot {new_slot_num} has reached maximum capacity.",
            "lock_acquisition_order": lock_order,
            "pcb_telemetry": realloc_res.get("pcb_telemetry", {})
        }), 409

    return jsonify({
        "error": status_code,
        "status_code": status_code,
        "message": f"Could not reschedule slot: {status_code}",
        "lock_acquisition_order": lock_order,
        "pcb_telemetry": realloc_res.get("pcb_telemetry", {})
    }), 400

