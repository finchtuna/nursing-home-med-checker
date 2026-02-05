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
    # New categories for Diana-style rules
    PPI_LONG_TERM = "PPI_LONG_TERM"
    RENAL_MONITORING = "RENAL_MONITORING"
    HIGH_RISK_MEDICATION = "HIGH_RISK_MEDICATION"
    CONTRAINDICATION = "CONTRAINDICATION"
    ANTICOAGULANT_MONITORING = "ANTICOAGULANT_MONITORING"
    ASPIRIN_ANTICOAGULANT = "ASPIRIN_ANTICOAGULANT"
    SEIZURE_CONTRAINDICATION = "SEIZURE_CONTRAINDICATION"
    DIGOXIN_INTERACTION = "DIGOXIN_INTERACTION"
    URINARY_RETENTION_RISK = "URINARY_RETENTION_RISK"
    ADMINISTRATION_TIMING = "ADMINISTRATION_TIMING"
    STEROID_INHALER_CARE = "STEROID_INHALER_CARE"
    DUPLICATE_PRN = "DUPLICATE_PRN"
    UNUSED_PRN = "UNUSED_PRN"
    ALLERGY_CONFLICT = "ALLERGY_CONFLICT"
    HOLD_PARAMETER_MISMATCH = "HOLD_PARAMETER_MISMATCH"
    SUPPLEMENT_UNNECESSARY = "SUPPLEMENT_UNNECESSARY"
    VAGUE_DIAGNOSIS = "VAGUE_DIAGNOSIS"
    TOPICAL_STEROID_DURATION = "TOPICAL_STEROID_DURATION"
    NALOXONE_WITHOUT_OPIOID = "NALOXONE_WITHOUT_OPIOID"
    ANTIBIOTIC_STEWARDSHIP = "ANTIBIOTIC_STEWARDSHIP"
    POTASSIUM_ADMINISTRATION = "POTASSIUM_ADMINISTRATION"
    FORMULATION_MISMATCH = "FORMULATION_MISMATCH"
    SUZETRIGINE_DURATION = "SUZETRIGINE_DURATION"
    GDR_ASSESSMENT = "GDR_ASSESSMENT"
    NEW_ADMISSION_PSYCHOTROPIC = "NEW_ADMISSION_PSYCHOTROPIC"


class RecommendationRouting(str, Enum):
    """Where the recommendation should be routed."""
    MD_PRIMARY = "MD_PRIMARY"
    MD_PSYCHIATRIST = "MD_PSYCHIATRIST"
    NURSING = "NURSING"
    ANTIBIOTIC_STEWARDSHIP = "ANTIBIOTIC_STEWARDSHIP"


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
    # New fields for Diana-style reports
    dob: Optional[date_type] = None
    room: Optional[str] = None
    care_center: Optional[str] = None
    attending_physician: Optional[str] = None
    psychiatrist: Optional[str] = None
    is_new_admission: bool = False


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
    # New fields for Diana-style rules
    last_used_date: Optional[date_type] = None
    stop_date: Optional[date_type] = None
    hold_parameters: Optional[str] = None
    administration_time: Optional[str] = None
    formulation: Optional[str] = None
    # PCC format fields
    duration_days: Optional[int] = None
    max_daily_dose: Optional[str] = None
    administration_instructions: Optional[str] = None


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
    # New fields for Diana-style reports
    routing: RecommendationRouting = RecommendationRouting.MD_PRIMARY
    diana_narrative: Optional[str] = None
    obra_reference: Optional[str] = None
    monitoring_parameters: Optional[str] = None


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
