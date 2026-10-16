"""
Flask Server Runner
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: backend/run.py

Starts the Flask development server on port 5000 (or PORT env var).
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true")
    print(f"Starting Smart Polling Platform Backend on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
