"""
Apple Interaction and Animation Experience Tests
Validates fluid transitions, Apple-style easing curves, tactile feedback styles,
and accessibility reduced-motion rules across VoteIT stylesheets and scripts.
"""

import os
import re
import pytest

CSS_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "css", "styles.css")
JS_VOTER_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "voter_portal.js")
JS_API_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "api_client.js")


def test_apple_easing_variables_present():
    """Verify Apple cubic-bezier easing definitions in CSS custom properties."""
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "--ease-apple:" in content
    assert "cubic-bezier(0.22, 1, 0.36, 1)" in content
    assert "--ease-apple-spring:" in content
    assert "cubic-bezier(0.34, 1.56, 0.64, 1)" in content


def test_workflow_step_transition_keyframes():
    """Verify workflow step animations and classes."""
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".workflow-step-active" in content
    assert "@keyframes workflowStepIn" in content
    assert "translateY(12px)" in content
    assert "var(--ease-apple)" in content


def test_tactile_feedback_microinteractions():
    """Verify button and card active/hover states with smooth transforms."""
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Primary & Secondary button active states
    assert ".btn-primary:active:not(:disabled)" in content
    assert "scale(0.985)" in content
    assert ".btn-secondary:active:not(:disabled)" in content

    # Booth and Slot cards
    assert ".booth-card:hover" in content
    assert "translateY(-2px)" in content
    assert ".slot-card.selected" in content
    assert "scale(1.01)" in content


def test_toast_and_disha_drawer_animations():
    """Verify toast notification entrance and Ask-DISHA drawer fluid motion."""
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "@keyframes toastSlideUp" in content
    assert "@keyframes dishaDrawerIn" in content
    assert "var(--ease-apple)" in content


def test_reduced_motion_accessibility():
    """Verify @media (prefers-reduced-motion: reduce) compliance."""
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "@media (prefers-reduced-motion: reduce)" in content
    assert "animation-duration: 0.01ms" in content or "animation: none" in content


def test_voter_portal_step_animation_trigger():
    """Verify JavaScript triggers Apple smooth transitions on step change."""
    with open(JS_VOTER_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "workflow-step-active" in content
    assert "void sec.offsetWidth" in content
    assert "appointment-slip-enter" in content


def test_zero_emojis_in_frontend():
    """Strict test ensuring 0 emojis are present across all modified frontend code."""
    emoji_pattern = re.compile(
        r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50\u2b55]'
    )
    for path in [CSS_PATH, JS_VOTER_PATH, JS_API_PATH]:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        matches = emoji_pattern.findall(text)
        assert len(matches) == 0, f"Found {len(matches)} emojis in {path}: {matches}"
