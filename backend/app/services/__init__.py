"""
Services Package Initializer
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Exports core business and logistical services:
  1. AuthService: JWT admin auth & simulated voter verification.
  2. VoterService: Synthetic voter registry & jurisdictional queries.
  3. BoothService: Booth, station, constituency & live occupancy views.
  4. AllocationService: Concurrency-safe atomic slot allocation, cancellation, and pass slip generation.
"""

from backend.app.services.auth_service import AuthService, auth_service
from backend.app.services.voter_service import VoterService, voter_service
from backend.app.services.booth_service import BoothService, booth_service
from backend.app.services.allocation_service import AllocationService, allocation_service
from backend.app.services.crowd_prediction_service import CrowdPredictionService, crowd_prediction_service
from backend.app.services.verification_service import VerificationService, verification_service
from backend.app.services.geo_booth_ranker import GeoBoothRanker, geo_booth_ranker

__all__ = [
    "AuthService",
    "auth_service",
    "VoterService",
    "voter_service",
    "BoothService",
    "booth_service",
    "AllocationService",
    "allocation_service",
    "CrowdPredictionService",
    "crowd_prediction_service",
    "VerificationService",
    "verification_service",
    "GeoBoothRanker",
    "geo_booth_ranker"
]
