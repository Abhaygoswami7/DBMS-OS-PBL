"""
AI Crowd Prediction & Smart Slot Recommendation Service
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/app/services/crowd_prediction_service.py

Loads trained Machine Learning artifacts:
  - ml_pipeline/artifacts/rf_crowd_model.joblib
  - ml_pipeline/artifacts/feature_scaler.joblib
  - ml_pipeline/artifacts/evaluation_metrics.json

Provides:
  1. predict_slot_demand(booth_id, slot_row):
     Computes predicted arrivals, predicted load percentage, estimated wait time,
     congestion level (LOW, MODERATE, HIGH, CRITICAL), and prediction source.
  2. recommend_optimal_slot(voter_id, lat, lon, accessibility_needed):
     Combines Haversine distance, remaining slot capacity, and AI predicted crowd load
     to recommend the optimal booth and slot with an explainable reason.
  3. Automatic Rule-Based Fallback:
     Seamlessly degrades to rule-based heuristic when ML artifacts are absent/disabled.
  4. Mandatory Legal Guardrail:
     Explicit assertion that AI predictions are advisory for queue load balancing only
     and NEVER determine voter eligibility or deny access to voting.
"""

import os
import math
import json
import joblib
import logging
import datetime
from typing import Dict, Any, Optional, List, Tuple
from database.db_pool import db_pool
from backend.app.services.booth_service import booth_service
from backend.app.services.voter_service import voter_service

logger = logging.getLogger("crowd_prediction_service")

# Mandatory Legal Guardrail Text
LEGAL_GUARDRAIL_ADVISORY = (
    "AI crowd predictions are advisory for queue load-balancing and staffing only, "
    "and never determine voter eligibility or deny access to voting."
)

FEATURE_COLUMNS = [
    "booth_id",
    "hour_of_day",
    "slot_max_capacity",
    "priority_reserved_capacity",
    "historical_avg_arrivals",
    "confirmed_bookings_count",
    "is_peak_morning_wave",
    "is_post_lunch_wave",
    "weather_comfort_index",
    "onoe_dual_ballot_factor"
]

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2 +
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(R * c, 3)

class CrowdPredictionService:
    """Service providing ML crowd forecasting, rule-based fallback, and smart slot load balancing."""

    def __init__(self):
        self.artifacts_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml_pipeline", "artifacts")
        )
        self.rf_model = None
        self.scaler = None
        self.evaluation_metrics = None
        self._load_artifacts()

    def _load_artifacts(self):
        """Attempts to load trained Scikit-Learn Random Forest and Scaler artifacts."""
        try:
            rf_path = os.path.join(self.artifacts_dir, "rf_crowd_model.joblib")
            scaler_path = os.path.join(self.artifacts_dir, "feature_scaler.joblib")
            metrics_path = os.path.join(self.artifacts_dir, "evaluation_metrics.json")

            if os.path.exists(rf_path) and os.path.exists(scaler_path):
                self.rf_model = joblib.load(rf_path)
                self.scaler = joblib.load(scaler_path)
                logger.info("Successfully loaded ML model and feature scaler from artifacts.")

            if os.path.exists(metrics_path):
                with open(metrics_path, "r", encoding="utf-8") as f:
                    self.evaluation_metrics = json.load(f)
        except Exception as e:
            logger.warning("Could not load ML artifacts: %s. Rule-based fallback active.", e)
            self.rf_model = None
            self.scaler = None

    def is_ml_enabled(self) -> bool:
        """Checks if ML is active and not explicitly disabled via ML_FALLBACK_ENABLED."""
        fallback_forced = os.getenv("ML_FALLBACK_ENABLED", "false").lower() in ("true", "1", "yes")
        return (not fallback_forced) and (self.rf_model is not None) and (self.scaler is not None)

    # -------------------------------------------------------------------------
    # 1. PREDICT SLOT DEMAND
    # -------------------------------------------------------------------------
    def predict_slot_demand(self, booth_id: int, slot_row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predicts expected voter arrival demand, load percentage, wait time, and congestion.
        Falls back to rule-based logic if ML model is unavailable or disabled.
        """
        # Mandatory Legal Guardrail Assertion
        assert LEGAL_GUARDRAIL_ADVISORY is not None

        max_capacity = int(slot_row.get("max_capacity") or 40)
        allocated_count = int(slot_row.get("allocated_count") or 0)
        priority_cap = int(slot_row.get("priority_reserved_capacity") or 10)

        # Parse hour of day from start_time string (e.g. '07:00:00' -> 7, or '09:30:00' -> 9)
        start_time_str = str(slot_row.get("start_time", "08:00:00"))
        try:
            hour_of_day = int(start_time_str.split(":")[0])
        except (ValueError, IndexError):
            hour_of_day = 9

        is_peak_morning = 1 if 8 <= hour_of_day <= 11 else 0
        is_post_lunch = 1 if 14 <= hour_of_day <= 16 else 0

        # Weather comfort and ONOE factors
        weather_index = 0.90 if is_peak_morning else 0.75
        onoe_factor = 1.22
        historical_avg = float(max_capacity * 0.70)

        use_ml = self.is_ml_enabled()
        predicted_arrivals = 0.0
        prediction_source = "RANDOM_FOREST_ML"

        if use_ml:
            try:
                import pandas as pd
                features_df = pd.DataFrame([{
                    "booth_id": booth_id,
                    "hour_of_day": hour_of_day,
                    "slot_max_capacity": max_capacity,
                    "priority_reserved_capacity": priority_cap,
                    "historical_avg_arrivals": historical_avg,
                    "confirmed_bookings_count": allocated_count,
                    "is_peak_morning_wave": is_peak_morning,
                    "is_post_lunch_wave": is_post_lunch,
                    "weather_comfort_index": weather_index,
                    "onoe_dual_ballot_factor": onoe_factor
                }], columns=FEATURE_COLUMNS)
                scaled_features = self.scaler.transform(features_df)
                raw_prediction = float(self.rf_model.predict(scaled_features)[0])
                predicted_arrivals = round(max(float(allocated_count), raw_prediction), 1)
            except Exception as e:
                logger.warning("ML inference failed, using fallback: %s", e)
                use_ml = False

        if not use_ml:
            # Deterministic Rule-Based Capacity Balancing Fallback
            prediction_source = "RULE_BASED_FALLBACK"
            wave_multiplier = 1.25 if is_peak_morning else (1.10 if is_post_lunch else 0.90)
            baseline_voters = allocated_count + (max_capacity - allocated_count) * 0.40
            predicted_arrivals = round(max(float(allocated_count), baseline_voters * wave_multiplier), 1)

        # Calculate metrics
        predicted_load_pct = round((predicted_arrivals / max_capacity) * 100.0, 1)

        # Congestion Level
        if predicted_load_pct < 45.0:
            congestion_level = "LOW"
        elif predicted_load_pct < 75.0:
            congestion_level = "MODERATE"
        elif predicted_load_pct < 95.0:
            congestion_level = "HIGH"
        else:
            congestion_level = "CRITICAL"

        # Estimated Wait Time (minutes) modeling dual-ballot EVM processing
        wait_ratio = (predicted_load_pct / 100.0) ** 1.4
        estimated_wait_minutes = round(max(2.0, min(45.0, wait_ratio * 28.0)), 1)

        return {
            "booth_id": booth_id,
            "slot_id": slot_row.get("slot_id"),
            "slot_date": slot_row.get("slot_date"),
            "start_time": slot_row.get("start_time"),
            "end_time": slot_row.get("end_time"),
            "max_capacity": max_capacity,
            "allocated_count": allocated_count,
            "available_capacity": max(0, max_capacity - allocated_count),
            "predicted_arrivals": predicted_arrivals,
            "predicted_load_pct": predicted_load_pct,
            "estimated_wait_minutes": estimated_wait_minutes,
            "congestion_level": congestion_level,
            "prediction_source": prediction_source,
            "legal_guardrail": {
                "is_advisory_only": True,
                "statement": LEGAL_GUARDRAIL_ADVISORY
            }
        }

    # -------------------------------------------------------------------------
    # 2. SMART OPTIMAL SLOT RECOMMENDATION & LOAD BALANCING
    # -------------------------------------------------------------------------
    def recommend_optimal_slot(
        self,
        voter_id: Optional[int] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        accessibility_needed: bool = False
    ) -> Dict[str, Any]:
        """
        Recommends the best booth and time slot by evaluating:
        - Haversine distance from voter coordinates
        - Accessibility accommodation (wheelchair ramps)
        - Available remaining slot capacity
        - AI-predicted congestion and wait times
        """
        # Determine voter details and assigned booth if voter_id provided
        target_booth_id = None
        voter_name = "Voter"
        if voter_id:
            voter = voter_service.get_voter_by_id(voter_id)
            if voter:
                target_booth_id = voter.get("assigned_booth_id")
                voter_name = voter.get("full_name", "Voter")
                if voter.get("special_category") in ("PERSON_WITH_DISABILITY", "SENIOR_CITIZEN"):
                    accessibility_needed = True

        stations = booth_service.get_polling_stations()
        candidate_booths = []

        # If voter has assigned booth, prioritize that booth
        if target_booth_id:
            booths = booth_service.get_polling_booths()
            candidate_booths = [b for b in booths if b["booth_id"] == target_booth_id]

        if not candidate_booths:
            candidate_booths = booth_service.get_polling_booths()

        evaluated_slots = []

        for b in candidate_booths:
            booth_id = b["booth_id"]
            # Station coordinates and distance (fallback to Bhimtal academic reference)
            stn_lat = float(b.get("latitude") or 29.3444)
            stn_lon = float(b.get("longitude") or 79.5632)
            # Find station wheelchair ramp flag
            has_ramp = bool(b.get("has_wheelchair_ramp", 1))

            distance_km = 0.0
            if lat is not None and lon is not None:
                distance_km = haversine_distance_km(lat, lon, stn_lat, stn_lon)

            # Filter or penalize if accessibility required but no ramp
            if accessibility_needed and not has_ramp:
                continue

            slots = booth_service.get_time_slots_for_booth(booth_id=booth_id)
            for s in slots:
                avail_cap = s.get("available_capacity", 0)
                if avail_cap <= 0 or s.get("status") == "FULL":
                    continue

                # Run demand forecast
                forecast = self.predict_slot_demand(booth_id, s)

                # Composite heuristic score (lower is better):
                # distance weight (3.0), predicted congestion (0.5), capacity bonus (-0.2)
                score = (
                    (distance_km * 3.0) +
                    (forecast["predicted_load_pct"] * 0.5) -
                    (avail_cap * 0.2)
                )

                evaluated_slots.append({
                    "booth_id": booth_id,
                    "booth_name": b.get("booth_name"),
                    "station_name": b.get("station_name"),
                    "station_address": b.get("station_address"),
                    "slot_id": s["slot_id"],
                    "slot_date": s["slot_date"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "available_capacity": avail_cap,
                    "distance_km": distance_km,
                    "has_wheelchair_ramp": has_ramp,
                    "forecast": forecast,
                    "composite_score": round(score, 3)
                })

        if not evaluated_slots:
            return {
                "recommendation_found": False,
                "message": "No open slots available matching criteria.",
                "legal_guardrail": LEGAL_GUARDRAIL_ADVISORY
            }

        # Sort by composite score (lowest first)
        evaluated_slots.sort(key=lambda x: x["composite_score"])
        best_candidate = evaluated_slots[0]

        reason = (
            f"Recommended for {voter_name}: {best_candidate['station_name']} ({best_candidate['booth_name']}), "
            f"Slot {best_candidate['start_time']} - {best_candidate['end_time']} on {best_candidate['slot_date']}. "
            f"Has {best_candidate['available_capacity']} seats available with {best_candidate['forecast']['congestion_level']} "
            f"predicted crowd load ({best_candidate['forecast']['predicted_load_pct']}% utilization, "
            f"~{best_candidate['forecast']['estimated_wait_minutes']}m estimated wait) "
            f"located {best_candidate['distance_km']} km away."
        )

        return {
            "recommendation_found": True,
            "recommended_booth_id": best_candidate["booth_id"],
            "recommended_booth_name": best_candidate["booth_name"],
            "recommended_station_name": best_candidate["station_name"],
            "recommended_slot_id": best_candidate["slot_id"],
            "slot_date": best_candidate["slot_date"],
            "start_time": best_candidate["start_time"],
            "end_time": best_candidate["end_time"],
            "available_capacity": best_candidate["available_capacity"],
            "predicted_load_pct": best_candidate["forecast"]["predicted_load_pct"],
            "congestion_level": best_candidate["forecast"]["congestion_level"],
            "estimated_wait_minutes": best_candidate["forecast"]["estimated_wait_minutes"],
            "distance_km": best_candidate["distance_km"],
            "recommendation_reason": reason,
            "all_ranked_candidates": evaluated_slots[:5],
            "legal_guardrail": {
                "is_advisory_only": True,
                "statement": LEGAL_GUARDRAIL_ADVISORY
            }
        }

    # -------------------------------------------------------------------------
    # 3. GET EVALUATION METRICS REPORT
    # -------------------------------------------------------------------------
    def get_evaluation_metrics_report(self) -> Dict[str, Any]:
        """Returns the serialized training metrics for Baseline vs. Random Forest."""
        if not self.evaluation_metrics:
            self._load_artifacts()
        return self.evaluation_metrics or {
            "error": "Metrics artifact not found. Please run training pipeline first."
        }

# Singleton instance
crowd_prediction_service = CrowdPredictionService()
