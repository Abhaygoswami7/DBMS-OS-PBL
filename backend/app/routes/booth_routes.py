"""
Polling Booth and Available Time-Slot REST API Routes
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/routes/booth_routes.py

Endpoints:
  - GET /api/booths/nearby: Geospatial booth search, Haversine ranking, accessibility filtering.
  - GET /api/slots/available: Real-time slot availability enriched with AI crowd predictions and smart recommendation.
"""

from flask import Blueprint, request, jsonify
from backend.app.services.booth_service import booth_service
from backend.app.services.crowd_prediction_service import (
    crowd_prediction_service,
    haversine_distance_km,
    LEGAL_GUARDRAIL_ADVISORY
)

booth_bp = Blueprint("booth_bp", __name__)

from backend.app.services.geo_booth_ranker import geo_booth_ranker, haversine_distance_km

@booth_bp.route("/booths/nearby", methods=["GET"])
def get_nearby_booths():
    """
    GET /api/booths/nearby
    Query params:
      - lat: float (voter GPS latitude)
      - lon: float (voter GPS longitude)
      - constituency_id: optional int (filter by PC or AC)
      - pc_id: optional int (filter by Parliamentary Constituency)
      - ac_id: optional int (filter by Assembly Constituency)
      - requires_wheelchair_accessibility / accessibility_needed: optional bool ('true'/'1' requires ramp)
    Calculates Haversine distance and ranks booths by composite accessibility, proximity, and live capacity score.
    """
    lat_param = request.args.get("lat")
    lon_param = request.args.get("lon")
    constituency_param = request.args.get("constituency_id")
    pc_param = request.args.get("pc_id")
    ac_param = request.args.get("ac_id")
    
    # Check both requires_wheelchair_accessibility and accessibility_needed query flags
    req_access_param = request.args.get("requires_wheelchair_accessibility")
    legacy_access_param = request.args.get("accessibility_needed")
    accessibility_flag = False
    if req_access_param is not None:
        accessibility_flag = req_access_param.lower() in ("true", "1", "yes")
    elif legacy_access_param is not None:
        accessibility_flag = legacy_access_param.lower() in ("true", "1", "yes")

    # Validate coordinates if provided (default to Bhimtal academic reference)
    try:
        user_lat = float(lat_param) if lat_param is not None else 29.3444
        user_lon = float(lon_param) if lon_param is not None else 79.5632
    except (ValueError, TypeError):
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Invalid latitude or longitude coordinates.",
            "status_code": 400
        }), 400

    constituency_id = None
    if constituency_param is not None:
        try:
            constituency_id = int(constituency_param)
        except ValueError:
            return jsonify({
                "error": "BAD_REQUEST",
                "message": "Invalid constituency_id parameter. Must be an integer.",
                "status_code": 400
            }), 400

    pc_id = None
    if pc_param is not None:
        try:
            pc_id = int(pc_param)
        except ValueError:
            return jsonify({
                "error": "BAD_REQUEST",
                "message": "Invalid pc_id parameter. Must be an integer.",
                "status_code": 400
            }), 400

    ac_id = None
    if ac_param is not None:
        try:
            ac_id = int(ac_param)
        except ValueError:
            return jsonify({
                "error": "BAD_REQUEST",
                "message": "Invalid ac_id parameter. Must be an integer.",
                "status_code": 400
            }), 400

    # Delegate to GeoBoothRanker for Haversine distance and multi-criteria composite ranking
    ranked_booths = geo_booth_ranker.rank_booths(
        user_lat=user_lat,
        user_lon=user_lon,
        constituency_id=constituency_id,
        requires_wheelchair_accessibility=accessibility_flag,
        pc_id=pc_id,
        ac_id=ac_id
    )

    return jsonify({
        "success": True,
        "query_reference": {
            "latitude": user_lat,
            "longitude": user_lon,
            "constituency_id": constituency_id,
            "pc_id": pc_id,
            "ac_id": ac_id,
            "requires_wheelchair_accessibility": accessibility_flag,
            "accessibility_needed": accessibility_flag
        },
        "total_booths_found": len(ranked_booths),
        "booths": ranked_booths
    }), 200


@booth_bp.route("/slots/available", methods=["GET"])
def get_available_slots():
    """
    GET /api/slots/available
    Query params:
      - booth_id: int (required)
      - event_id: int (optional, default 1)
      - voter_id: int (optional, for personalized smart slot recommendation)
    Returns discretized time slots enriched with confirmed bookings, AI predicted crowd demand,
    and smart slot load-balancing recommendation.
    """
    booth_id_param = request.args.get("booth_id")
    event_id_param = request.args.get("event_id", "1")
    voter_id_param = request.args.get("voter_id")

    if not booth_id_param:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Missing required query parameter: 'booth_id'.",
            "status_code": 400
        }), 400

    try:
        booth_id = int(booth_id_param)
        event_id = int(event_id_param)
        voter_id = int(voter_id_param) if voter_id_param else None
    except ValueError:
        return jsonify({
            "error": "BAD_REQUEST",
            "message": "Parameters 'booth_id', 'event_id', and 'voter_id' must be valid integers.",
            "status_code": 400
        }), 400

    # Verify booth existence
    all_booths = booth_service.get_polling_booths()
    booth_info = next((b for b in all_booths if b["booth_id"] == booth_id), None)
    if not booth_info:
        return jsonify({
            "error": "NOT_FOUND",
            "message": f"Polling booth with booth_id {booth_id} not found.",
            "status_code": 404
        }), 404

    # Fetch slots for this booth
    slots = booth_service.get_time_slots_for_booth(booth_id=booth_id, event_id=event_id)

    # Compute optimal slot recommendation for this voter/booth
    recommendation = crowd_prediction_service.recommend_optimal_slot(
        voter_id=voter_id
    )
    recommended_slot_id = recommendation.get("recommended_slot_id")

    enriched_slots = []
    for s in slots:
        max_cap = s.get("max_capacity", 40)
        allocated = s.get("allocated_count", 0)
        available = max(0, max_cap - allocated)

        # Operational status
        if allocated >= max_cap:
            occupancy_status = "FULL"
        elif allocated > 0:
            occupancy_status = "PARTIALLY_OCCUPIED"
        else:
            occupancy_status = "AVAILABLE"

        # AI Demand Forecast
        forecast = crowd_prediction_service.predict_slot_demand(booth_id, s)

        is_recommended = (s["slot_id"] == recommended_slot_id)

        enriched_slots.append({
            "slot_id": s["slot_id"],
            "booth_id": booth_id,
            "event_id": event_id,
            "slot_date": s["slot_date"],
            "start_time": s["start_time"],
            "end_time": s["end_time"],
            "max_capacity": max_cap,
            "allocated_count": allocated,
            "available_capacity": available,
            "utilization_pct": s.get("utilization_pct", 0.0),
            "priority_reserved_capacity": s.get("priority_reserved_capacity", 10),
            "occupancy_status": occupancy_status,
            "is_recommended": is_recommended,
            "ai_crowd_forecast": {
                "predicted_arrivals": forecast["predicted_arrivals"],
                "predicted_load_pct": forecast["predicted_load_pct"],
                "estimated_wait_minutes": forecast["estimated_wait_minutes"],
                "congestion_level": forecast["congestion_level"],
                "prediction_source": forecast["prediction_source"]
            }
        })

    return jsonify({
        "success": True,
        "booth": {
            "booth_id": booth_info["booth_id"],
            "booth_number": booth_info["booth_number"],
            "booth_name": booth_info["booth_name"],
            "station_name": booth_info["station_name"],
            "parliamentary_constituency": booth_info["parliamentary_constituency"],
            "assembly_constituency": booth_info["assembly_constituency"]
        },
        "recommendation": {
            "recommended_slot_id": recommended_slot_id,
            "recommendation_reason": recommendation.get("recommendation_reason")
        },
        "legal_guardrail": {
            "is_advisory_only": True,
            "statement": LEGAL_GUARDRAIL_ADVISORY
        },
        "slots_count": len(enriched_slots),
        "slots": enriched_slots
    }), 200
