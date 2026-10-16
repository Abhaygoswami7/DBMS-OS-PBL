"""
Routes Package Initializer
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Exports modular Flask Blueprints:
  1. auth_bp: /api/auth
  2. voter_bp: /api (voter registration & verification)
  3. booth_bp: /api (nearby booths & available slots)
  4. allocation_bp: /api (slot allocations, slips, cancellations)
  5. admin_bp: /api/admin (dashboard, booths, slots, crowd predictions)
"""

from backend.app.routes.auth_routes import auth_bp
from backend.app.routes.voter_routes import voter_bp
from backend.app.routes.booth_routes import booth_bp
from backend.app.routes.allocation_routes import allocation_bp
from backend.app.routes.admin_routes import admin_bp

__all__ = [
    "auth_bp",
    "voter_bp",
    "booth_bp",
    "allocation_bp",
    "admin_bp"
]
