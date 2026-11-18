"""
CLI Tool: Display and Export 20 Persistent Demo Voter Accounts
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: database/export_demo_voters.py

Usage:
  python database/export_demo_voters.py
  python database/export_demo_voters.py --json export.json
  python database/export_demo_voters.py --csv export.csv

Safe for demonstration and academic evaluation: Excludes admin credentials.
"""

import sys
import os
import argparse
import json
import csv
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.app.services.demo_voter_service import demo_voter_service

def main():
    parser = argparse.ArgumentParser(description="Display and export 20 persistent demo voter accounts.")
    parser.add_argument("--json", type=str, help="Export demo accounts to specified JSON file path")
    parser.add_argument("--csv", type=str, help="Export demo accounts to specified CSV file path")
    args = parser.parse_args()

    # Ensure accounts are seeded in database
    demo_voter_service.ensure_demo_voters_seeded()
    voters = demo_voter_service.get_all_demo_voters()

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({
                "meta": {
                    "total": len(voters),
                    "description": "20 Persistent Demo Voter Accounts (One Nation One Election Prototype)"
                },
                "demo_voters": voters
            }, f, indent=2)
        print(f"[+] Successfully exported {len(voters)} demo accounts to JSON: {args.json}")
        return

    if args.csv:
        fieldnames = [
            "voter_id", "full_name", "formatted_id", "synthetic_aadhaar_id",
            "demo_epic_no", "special_category", "priority_tier", "assigned_booth_id", "station_name"
        ]
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for v in voters:
                writer.writerow(v)
        print(f"[+] Successfully exported {len(voters)} demo accounts to CSV: {args.csv}")
        return

    # Default: Pretty-print terminal table
    print("=" * 105)
    print(" VOTEIT - 20 PERSISTENT SYNTHETIC DEMO VOTER ACCOUNTS")
    print("=" * 105)
    header = f"{'ID':<4} | {'Synthetic Demo Aadhaar':<16} | {'Demo EPIC':<18} | {'Voter Name':<24} | {'Tier':<4} | {'Category':<22}"
    print(header)
    print("-" * 105)
    for v in voters:
        print(f"{v['voter_id']:<4} | {v['formatted_id']:<16} | {v['demo_epic_no']:<18} | {v['full_name']:<24} | {v['priority_tier']:<4} | {v['special_category']:<22}")
    print("=" * 105)
    print("Note: All IDs are 100% synthetic demo identifiers. Passwords and admin keys are never displayed.")
    print("=" * 105)

if __name__ == "__main__":
    main()
