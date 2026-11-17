"""
Centralized Category & Priority Constants
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)

Project-Defined Priority Hierarchy:
  P1: Pregnant Women (Highest)            -> priority_level = 1
  P2: Persons with Disabilities (PwD)     -> priority_level = 2
  P3: Senior Citizens                     -> priority_level = 3
  P4: General Voters                      -> priority_level = 4

CONSTITUTIONAL & DEMO DISCLAIMER:
These priorities model assistive queuing and server-side request dispatching
for logistics demonstration only; they do not alter constitutional franchise.
"""

from typing import Dict, Any

CATEGORY_PRIORITY_MAP: Dict[str, int] = {
    "PREGNANT_WOMEN": 1,
    "PERSON_WITH_DISABILITY": 2,
    "SENIOR_CITIZEN": 3,
    "GENERAL": 4
}

PRIORITY_LABEL_MAP: Dict[int, str] = {
    1: "P1 - Pregnant Women",
    2: "P2 - Persons with Disabilities (PwD)",
    3: "P3 - Senior Citizens",
    4: "P4 - General Voters"
}

PRIORITY_LABELS = PRIORITY_LABEL_MAP
PRIORITY_LEVELS = (1, 2, 3, 4)

PRIORITY_CATEGORY_NAME_MAP: Dict[str, str] = {
    "PREGNANT_WOMEN": "Pregnant Women",
    "PERSON_WITH_DISABILITY": "Persons with Disabilities (PwD)",
    "SENIOR_CITIZEN": "Senior Citizens",
    "GENERAL": "General Voters"
}

# Base priorities for OS Scheduling & Simulation (1.0 = highest, 4.0 = normal)
CATEGORY_BASE_PRIORITY_MAP: Dict[str, float] = {
    "PREGNANT_WOMEN": 1.0,
    "PERSON_WITH_DISABILITY": 2.0,
    "SENIOR_CITIZEN": 3.0,
    "GENERAL": 4.0
}

def get_priority_for_category(category: str) -> int:
    """Returns integer priority 1..4 for a given category name."""
    if not category:
        return 4
    return CATEGORY_PRIORITY_MAP.get(category.strip().upper(), 4)

def get_base_priority_float(category: str) -> float:
    """Returns float base priority (1.0..4.0) for OS scheduler."""
    if not category:
        return 4.0
    return CATEGORY_BASE_PRIORITY_MAP.get(category.strip().upper(), 4.0)
