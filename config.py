"""Configuration and API setup for LTC medication reconciliation."""

import os
from anthropic import Anthropic

# API Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Model configuration
PARSING_MODEL = "claude-sonnet-4-20250514"
NARRATIVE_MODEL = "claude-sonnet-4-20250514"

# Complexity thresholds
COMPLEXITY_THRESHOLDS = {
    "EASY": 5,
    "MEDIUM": 15,
    # HARD: > 15
}

# Lab monitoring intervals (days)
LAB_MONITORING_INTERVALS = {
    "INR": 30,  # Monthly for warfarin
    "CBC": 90,  # Quarterly
    "CMP": 90,  # Quarterly (includes BMP)
    "BMP": 90,
    "TSH": 180,  # Semi-annually
    "HbA1c": 90,  # Quarterly for diabetics
    "lithium_level": 90,
    "valproic_acid_level": 90,
    "phenytoin_level": 90,
    "digoxin_level": 180,
}

# GDR timeline (days)
GDR_OVERDUE_DAYS = 180  # 6 months


def get_anthropic_client() -> Anthropic:
    """Get configured Anthropic client."""
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please set it with: set ANTHROPIC_API_KEY=your_key_here"
        )
    return Anthropic(api_key=ANTHROPIC_API_KEY)
