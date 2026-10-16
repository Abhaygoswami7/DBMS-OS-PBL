"""
Stage 5 Documentation Integrity Test Suite
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Module: tests/test_stage5_docs_integrity.py

Validates that:
  1. All 4 core documentation artifacts exist and are non-empty:
     - docs/01_Complete_Academic_Synopsis.md
     - docs/02_Concise_College_Synopsis.md
     - docs/DATABASE_SPECIFICATION.md
     - docs/06_System_Diagrams_Mermaid.md
  2. docs/01_Complete_Academic_Synopsis.md contains all 29 mandatory numbered section headers (## 1. through ## 29.).
  3. All 11 MySQL table names, all 3 stored procedures, all 9 OS concepts, and all 12 REST API routes are documented.
  4. docs/06_System_Diagrams_Mermaid.md contains at least 9 valid Mermaid diagram blocks covering all required diagrams.
  5. Strict academic and legal guardrails are explicitly articulated (logistics-only scope, synthetic identifiers, advisory time slots).
"""

import os
import re
import pytest

DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))

FILE_01 = os.path.join(DOCS_DIR, "01_Complete_Academic_Synopsis.md")
FILE_02 = os.path.join(DOCS_DIR, "02_Concise_College_Synopsis.md")
FILE_DB = os.path.join(DOCS_DIR, "DATABASE_SPECIFICATION.md")
FILE_06 = os.path.join(DOCS_DIR, "06_System_Diagrams_Mermaid.md")


def test_docs_files_exist_and_non_empty():
    """Verify that all 4 documentation files exist and exceed minimum byte size thresholds."""
    for path in [FILE_01, FILE_02, FILE_DB, FILE_06]:
        assert os.path.exists(path), f"Missing documentation file: {path}"
        size = os.path.getsize(path)
        assert size > 500, f"Documentation file {os.path.basename(path)} is unexpectedly small ({size} bytes)"


def test_synopsis_29_sections_present():
    """Verify that docs/01_Complete_Academic_Synopsis.md contains all 29 numbered section headers."""
    with open(FILE_01, "r", encoding="utf-8") as f:
        content = f.read()

    expected_sections = [
        "1. Title Page",
        "2. Abstract",
        "3. Introduction",
        "4. Background and Motivation",
        "5. Problem Statement",
        "6. Existing System and Its Limitations",
        "7. Proposed System",
        "8. Aim and Objectives",
        "9. Project Scope and Exclusions",
        "10. Functional Requirements",
        "11. Non-Functional Requirements",
        "12. Feasibility Study",
        "13. Literature Review and Related Work",
        "14. Proposed Methodology",
        "15. System Architecture",
        "16. Operating Systems Concepts and Implementation",
        "17. DBMS Design and Normalization",
        "18. AI/ML Methods and Algorithm Design",
        "19. Technology Stack and Software Requirements",
        "20. Hardware Requirements",
        "21. API Design",
        "22. Project Diagrams",
        "23. Testing and Evaluation Plan",
        "24. Expected Outcomes",
        "25. Limitations and Assumptions",
        "26. Privacy, Security, Fairness, and Legal Considerations",
        "27. Future Enhancements",
        "28. Project Timeline with Milestones",
        "29. References",
    ]

    for section in expected_sections:
        header = f"## {section}"
        assert header in content, f"Missing mandatory section header: '{header}' in docs/01_Complete_Academic_Synopsis.md"


def test_synopsis_contains_all_11_tables_and_procedures():
    """Verify that docs/01_Complete_Academic_Synopsis.md accurately documents all 11 tables and 3 stored procedures."""
    with open(FILE_01, "r", encoding="utf-8") as f:
        content = f.read()

    expected_tables = [
        "states",
        "constituencies",
        "polling_stations",
        "polling_booths",
        "voters",
        "election_events",
        "time_slots",
        "slot_allocations",
        "simulated_verifications",
        "crowd_telemetry",
        "os_concurrency_audit"
    ]

    for table in expected_tables:
        assert table in content, f"Table '{table}' not found in docs/01_Complete_Academic_Synopsis.md"

    expected_procedures = [
        "sp_allocate_slot_atomic",
        "sp_cancel_slot_atomic",
        "sp_log_os_concurrency_event"
    ]

    for sp in expected_procedures:
        assert sp in content, f"Stored procedure '{sp}' not found in docs/01_Complete_Academic_Synopsis.md"


def test_synopsis_contains_all_9_os_concepts():
    """Verify that docs/01_Complete_Academic_Synopsis.md details all 9 mandatory OS concepts."""
    with open(FILE_01, "r", encoding="utf-8") as f:
        content = f.read()

    expected_concepts = [
        "Process Management",
        "CPU Scheduling",
        "Mutual Exclusion",
        "Critical Section",
        "Race Conditions",
        "Synchronization",
        "Deadlock",
        "Resource Allocation",
        "Memory Management"
    ]

    for concept in expected_concepts:
        assert concept.lower() in content.lower(), f"OS Concept '{concept}' missing from docs/01_Complete_Academic_Synopsis.md"


def test_synopsis_contains_all_12_api_routes():
    """Verify that all 12 core REST API endpoints are documented in docs/01_Complete_Academic_Synopsis.md."""
    with open(FILE_01, "r", encoding="utf-8") as f:
        content = f.read()

    expected_routes = [
        "/api/auth/login",
        "/api/voters/register",
        "/api/verification/mock",
        "/api/booths/nearby",
        "/api/slots/available",
        "/api/allocations",
        "/api/admin/dashboard",
        "/api/admin/booths",
        "/api/admin/slots",
        "/api/admin/crowd-predictions",
        "/api/health",
        "/api/admin/simulate-race"
    ]

    for route in expected_routes:
        assert route in content, f"REST API Route '{route}' missing from docs/01_Complete_Academic_Synopsis.md"


def test_diagrams_document_contains_all_9_mermaid_diagrams():
    """Verify that docs/06_System_Diagrams_Mermaid.md contains at least 9 valid Mermaid diagram blocks."""
    with open(FILE_06, "r", encoding="utf-8") as f:
        content = f.read()

    mermaid_blocks = re.findall(r"```mermaid(.*?)```", content, re.DOTALL)
    assert len(mermaid_blocks) >= 9, f"Expected at least 9 Mermaid diagrams, found {len(mermaid_blocks)}"

    required_keywords = [
        "System Architecture",
        "Data Flow Diagram",
        "Entity-Relationship",
        "Use-Case",
        "Activity Diagram",
        "Sequence Diagram",
        "Flowchart",
        "Deployment Diagram",
        "State Diagram"
    ]

    for kw in required_keywords:
        assert kw.lower() in content.lower(), f"Diagram topic '{kw}' missing from docs/06_System_Diagrams_Mermaid.md"


def test_concise_synopsis_verification_checklist():
    """Verify that docs/02_Concise_College_Synopsis.md contains the complete prototype implementation checklist."""
    with open(FILE_02, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Final Prototype Implementation Verification Checklist" in content
    assert "Strict Academic & Legal Guardrails" in content
    assert "10-Week Implementation Schedule" in content
    assert "VERIFIED" in content
