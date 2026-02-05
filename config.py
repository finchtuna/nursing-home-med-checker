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

# Diana-style clinical thresholds
PPI_LONG_TERM_DAYS = 56  # 8 weeks per OBRA guidelines
UNUSED_PRN_DAYS = 90  # Flag PRN meds not used in 90 days
NEW_ADMISSION_WINDOW_DAYS = 30  # New admission review window
SUZETRIGINE_MAX_DAYS = 14  # Suzetrigine max recommended duration
TOPICAL_STEROID_REVIEW_DAYS = 30  # Review topical steroids after 30 days

# Allergy cross-reactivity mapping
ALLERGY_CROSS_REACTIVITY = {
    "penicillin": ["amoxicillin", "ampicillin", "augmentin", "piperacillin"],
    "sulfa": ["sulfamethoxazole", "trimethoprim-sulfamethoxazole", "sulfasalazine", "bactrim"],
    "aspirin": ["ketorolac", "ibuprofen", "naproxen", "celecoxib", "meloxicam"],
    "codeine": ["morphine", "hydrocodone", "oxycodone", "hydromorphone"],
    "cephalosporin": ["cefazolin", "cephalexin", "ceftriaxone", "cefepime"],
}


def get_anthropic_client() -> Anthropic:
    """Get configured Anthropic client."""
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please set it with: set ANTHROPIC_API_KEY=your_key_here"
        )
    return Anthropic(api_key=ANTHROPIC_API_KEY)
