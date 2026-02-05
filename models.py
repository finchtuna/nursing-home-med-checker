"""Pydantic data models for LTC medication reconciliation."""

from datetime import date as date_type
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Clinical flag severity levels."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FlagCategory(str, Enum):
    """Categories for clinical flags."""
    INDICATION = "INDICATION"
    LAB_MONITORING = "LAB_MONITORING"
    DRUG_INTERACTION = "DRUG_INTERACTION"
    BEERS_CRITERIA = "BEERS_CRITERIA"
    ANTIPSYCHOTIC = "ANTIPSYCHOTIC"
    CONTROLLED_SUBSTANCE = "CONTROLLED_SUBSTANCE"
    FALL_RISK = "FALL_RISK"
    PROPHYLAXIS = "PROPHYLAXIS"
    DUPLICATE_THERAPY = "DUPLICATE_THERAPY"


class ComplexityLevel(str, Enum):
    """Chart complexity levels."""
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class Patient(BaseModel):
    """Patient demographic and clinical information."""
    name: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    admission_date: Optional[date_type] = None
    diagnoses: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)


class Medication(BaseModel):
    """Medication record from EHR."""
    name: str  # Generic name (normalized)
    brand: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    indication: Optional[str] = None
    start_date: Optional[date_type] = None
    prescriber: Optional[str] = None
    drug_class: Optional[str] = None
    is_prn: bool = False
    schedule: Optional[str] = None  # DEA schedule (II, III, IV, V)


class LabResult(BaseModel):
    """Laboratory result record."""
    test_name: str
    value: Optional[float] = None
    value_text: Optional[str] = None  # For non-numeric results
    unit: Optional[str] = None
    date: Optional[date_type] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None  # H, L, CRITICAL, etc.


class ParsedChart(BaseModel):
    """Complete parsed chart data."""
    patient: Patient = Field(default_factory=Patient)
    medications: list[Medication] = Field(default_factory=list)
    labs: list[LabResult] = Field(default_factory=list)
    parsing_confidence: float = 1.0
    parsing_notes: list[str] = Field(default_factory=list)


class ClinicalFlag(BaseModel):
    """A clinical finding requiring attention."""
    severity: Severity
    category: FlagCategory
    finding: str
    significance: str
    recommendation: str
    prescriber_action_needed: bool = False
    medications_involved: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Complete analysis output."""
    flags: list[ClinicalFlag] = Field(default_factory=list)
    complexity_score: int = 0
    complexity_level: ComplexityLevel = ComplexityLevel.EASY

    # Summary counts
    total_medications: int = 0
    fall_risk_count: int = 0
    cns_depressant_count: int = 0
    anticholinergic_count: int = 0
    controlled_substance_count: int = 0
    antipsychotic_count: int = 0
    beers_count: int = 0

    # GDR tracking
    antipsychotics_needing_gdr: list[str] = Field(default_factory=list)

    # Lab monitoring
    labs_due: list[str] = Field(default_factory=list)
    labs_overdue: list[str] = Field(default_factory=list)
