"""Unit tests for clinical analysis engine."""

import pytest
from datetime import date, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import (
    ParsedChart, Patient, Medication, LabResult,
    ClinicalFlag, Severity, FlagCategory
)
from analyzer import (
    analyze_medications,
    check_indication_verification,
    check_lab_monitoring,
    check_drug_interactions,
    check_beers_criteria,
    check_antipsychotic_compliance,
    check_controlled_substances,
    check_fall_risk,
    check_missing_prophylaxis,
    calculate_complexity_score,
)


class TestIndicationVerification:
    """Tests for indication verification rules."""

    def test_antipsychotic_without_indication_flags_high(self):
        """Antipsychotic without indication should flag HIGH."""
        meds = [Medication(name="quetiapine", dose="25mg", frequency="at bedtime")]
        diagnoses = ["hypertension"]

        flags = check_indication_verification(meds, diagnoses)

        assert len(flags) >= 1
        high_flags = [f for f in flags if f.severity == Severity.HIGH]
        assert len(high_flags) >= 1
        assert "quetiapine" in high_flags[0].finding.lower()

    def test_antipsychotic_with_appropriate_indication_no_flag(self):
        """Antipsychotic with psychiatric indication should not flag for missing indication."""
        meds = [Medication(name="quetiapine", dose="25mg", indication="schizophrenia")]
        diagnoses = ["schizophrenia"]

        flags = check_indication_verification(meds, diagnoses)

        # Should not have HIGH flag for missing indication
        missing_indication_flags = [
            f for f in flags
            if f.severity == Severity.HIGH and "lacks documented indication" in f.finding
        ]
        assert len(missing_indication_flags) == 0

    def test_antipsychotic_for_insomnia_flags_inappropriate(self):
        """Antipsychotic for insomnia should flag as inappropriate."""
        meds = [Medication(name="quetiapine", dose="25mg", indication="insomnia")]
        diagnoses = ["insomnia"]

        flags = check_indication_verification(meds, diagnoses)

        inappropriate_flags = [f for f in flags if "inappropriate indication" in f.finding.lower()]
        assert len(inappropriate_flags) >= 1


class TestLabMonitoring:
    """Tests for lab monitoring rules."""

    def test_warfarin_without_inr_flags(self):
        """Warfarin without INR should flag."""
        meds = [Medication(name="warfarin", dose="5mg", frequency="daily")]
        labs = []

        flags = check_lab_monitoring(meds, labs)

        inr_flags = [f for f in flags if "inr" in f.finding.lower()]
        assert len(inr_flags) >= 1

    def test_warfarin_with_recent_inr_no_flag(self):
        """Warfarin with recent INR should not flag for missing INR."""
        meds = [Medication(name="warfarin", dose="5mg", frequency="daily")]
        labs = [LabResult(test_name="INR", value=2.5, date=date.today() - timedelta(days=7))]

        flags = check_lab_monitoring(meds, labs)

        # Should not flag for missing INR
        missing_inr_flags = [f for f in flags if "missing inr" in f.finding.lower()]
        assert len(missing_inr_flags) == 0

    def test_warfarin_with_old_inr_flags_overdue(self):
        """Warfarin with old INR should flag as overdue."""
        meds = [Medication(name="warfarin", dose="5mg", frequency="daily")]
        labs = [LabResult(test_name="INR", value=2.5, date=date.today() - timedelta(days=60))]

        flags = check_lab_monitoring(meds, labs)

        overdue_flags = [f for f in flags if "overdue" in f.finding.lower()]
        assert len(overdue_flags) >= 1


class TestDrugInteractions:
    """Tests for drug interaction rules."""

    def test_multiple_serotonergic_flags_syndrome_risk(self):
        """Multiple serotonergic medications should flag serotonin syndrome risk."""
        meds = [
            Medication(name="sertraline", dose="100mg"),
            Medication(name="tramadol", dose="50mg"),
        ]

        flags = check_drug_interactions(meds)

        serotonin_flags = [f for f in flags if "serotonin" in f.finding.lower()]
        assert len(serotonin_flags) >= 1
        assert serotonin_flags[0].severity == Severity.HIGH

    def test_multiple_qtc_prolonging_flags(self):
        """Multiple QTc-prolonging medications should flag."""
        meds = [
            Medication(name="quetiapine", dose="100mg"),
            Medication(name="citalopram", dose="20mg"),
        ]

        flags = check_drug_interactions(meds)

        qtc_flags = [f for f in flags if "qtc" in f.finding.lower()]
        assert len(qtc_flags) >= 1

    def test_cns_depression_stacking(self):
        """Three or more CNS depressants should flag."""
        meds = [
            Medication(name="lorazepam", dose="0.5mg"),
            Medication(name="quetiapine", dose="25mg"),
            Medication(name="trazodone", dose="50mg"),
        ]

        flags = check_drug_interactions(meds)

        cns_flags = [f for f in flags if "cns depression" in f.finding.lower()]
        assert len(cns_flags) >= 1
        assert cns_flags[0].severity == Severity.HIGH

    def test_high_anticholinergic_burden(self):
        """High anticholinergic burden should flag."""
        meds = [
            Medication(name="diphenhydramine", dose="25mg"),  # burden 3
            Medication(name="oxybutynin", dose="5mg"),  # burden 3
        ]

        flags = check_drug_interactions(meds)

        ach_flags = [f for f in flags if "anticholinergic burden" in f.finding.lower()]
        assert len(ach_flags) >= 1

    def test_duplicate_therapy_detection(self):
        """Duplicate therapy should be flagged."""
        meds = [
            Medication(name="lorazepam", dose="0.5mg"),
            Medication(name="alprazolam", dose="0.25mg"),
        ]

        flags = check_drug_interactions(meds)

        duplicate_flags = [f for f in flags if f.category == FlagCategory.DUPLICATE_THERAPY]
        assert len(duplicate_flags) >= 1


class TestBeersCriteria:
    """Tests for Beers Criteria rules."""

    def test_beers_list_medication_flags_elderly(self):
        """Beers list medication should flag for elderly patient."""
        meds = [Medication(name="diphenhydramine", dose="25mg")]

        flags = check_beers_criteria(meds, age=75)

        beers_flags = [f for f in flags if f.category == FlagCategory.BEERS_CRITERIA]
        assert len(beers_flags) >= 1
        assert beers_flags[0].severity == Severity.HIGH  # diphenhydramine is "avoid"

    def test_beers_list_no_flag_young_patient(self):
        """Beers list medication should not flag for young patient."""
        meds = [Medication(name="diphenhydramine", dose="25mg")]

        flags = check_beers_criteria(meds, age=45)

        beers_flags = [f for f in flags if f.category == FlagCategory.BEERS_CRITERIA]
        assert len(beers_flags) == 0

    def test_assumes_elderly_if_age_unknown(self):
        """Should assume elderly (and flag) if age unknown in LTC."""
        meds = [Medication(name="diphenhydramine", dose="25mg")]

        flags = check_beers_criteria(meds, age=None)

        beers_flags = [f for f in flags if f.category == FlagCategory.BEERS_CRITERIA]
        assert len(beers_flags) >= 1


class TestAntipsychoticCompliance:
    """Tests for antipsychotic compliance rules."""

    def test_multiple_antipsychotics_flags_high(self):
        """Multiple antipsychotics should flag HIGH."""
        meds = [
            Medication(name="quetiapine", dose="100mg"),
            Medication(name="risperidone", dose="1mg"),
        ]

        flags = check_antipsychotic_compliance(meds)

        multiple_flags = [f for f in flags if "multiple antipsychotics" in f.finding.lower()]
        assert len(multiple_flags) >= 1
        assert multiple_flags[0].severity == Severity.HIGH

    def test_gdr_overdue_flags(self):
        """Antipsychotic over 6 months should flag for GDR."""
        meds = [
            Medication(
                name="quetiapine",
                dose="100mg",
                start_date=date.today() - timedelta(days=200)
            )
        ]

        flags = check_antipsychotic_compliance(meds)

        gdr_flags = [f for f in flags if "gdr overdue" in f.finding.lower()]
        assert len(gdr_flags) >= 1

    def test_black_box_warning_info(self):
        """Antipsychotic should include black box warning info."""
        meds = [Medication(name="quetiapine", dose="100mg")]

        flags = check_antipsychotic_compliance(meds)

        bbw_flags = [f for f in flags if "black box" in f.finding.lower()]
        assert len(bbw_flags) >= 1
        assert bbw_flags[0].severity == Severity.INFO


class TestControlledSubstances:
    """Tests for controlled substance rules."""

    def test_opioid_plus_benzo_flags_high(self):
        """Concurrent opioid and benzodiazepine should flag HIGH."""
        meds = [
            Medication(name="oxycodone", dose="5mg"),
            Medication(name="lorazepam", dose="0.5mg"),
        ]

        flags = check_controlled_substances(meds)

        combo_flags = [f for f in flags if "opioid and benzodiazepine" in f.finding.lower()]
        assert len(combo_flags) >= 1
        assert combo_flags[0].severity == Severity.HIGH

    def test_prn_controlled_flags(self):
        """PRN controlled substances should flag."""
        meds = [
            Medication(name="lorazepam", dose="0.5mg", is_prn=True),
        ]

        flags = check_controlled_substances(meds)

        prn_flags = [f for f in flags if "prn controlled" in f.finding.lower()]
        assert len(prn_flags) >= 1


class TestFallRisk:
    """Tests for fall risk rules."""

    def test_multiple_fall_risk_meds_flags(self):
        """Three or more fall-risk medications should flag."""
        meds = [
            Medication(name="lorazepam", dose="0.5mg"),
            Medication(name="quetiapine", dose="25mg"),
            Medication(name="trazodone", dose="50mg"),
        ]

        flags = check_fall_risk(meds)

        fall_flags = [f for f in flags if f.category == FlagCategory.FALL_RISK]
        assert len(fall_flags) >= 1

    def test_five_or_more_fall_risk_flags_high(self):
        """Five or more fall-risk medications should flag HIGH."""
        meds = [
            Medication(name="lorazepam", dose="0.5mg"),
            Medication(name="quetiapine", dose="25mg"),
            Medication(name="trazodone", dose="50mg"),
            Medication(name="mirtazapine", dose="15mg"),
            Medication(name="gabapentin", dose="300mg"),
        ]

        flags = check_fall_risk(meds)

        fall_flags = [f for f in flags if f.category == FlagCategory.FALL_RISK]
        assert len(fall_flags) >= 1
        assert fall_flags[0].severity == Severity.HIGH


class TestMissingProphylaxis:
    """Tests for missing prophylaxis rules."""

    def test_opioid_without_bowel_regimen_flags(self):
        """Opioid without bowel regimen should flag."""
        meds = [Medication(name="oxycodone", dose="5mg")]

        flags = check_missing_prophylaxis(meds)

        bowel_flags = [f for f in flags if "bowel regimen" in f.finding.lower()]
        assert len(bowel_flags) >= 1

    def test_opioid_with_bowel_regimen_no_flag(self):
        """Opioid with bowel regimen should not flag for missing bowel regimen."""
        meds = [
            Medication(name="oxycodone", dose="5mg"),
            Medication(name="senna", dose="8.6mg"),
        ]

        flags = check_missing_prophylaxis(meds)

        bowel_flags = [f for f in flags if "bowel regimen" in f.finding.lower()]
        assert len(bowel_flags) == 0


class TestComplexityCalculation:
    """Tests for complexity score calculation."""

    def test_easy_complexity(self):
        """Few meds and no flags should be EASY."""
        meds = [
            Medication(name="lisinopril", dose="10mg"),
            Medication(name="metformin", dose="500mg"),
        ]
        flags = []

        score, level = calculate_complexity_score(flags, meds)

        assert level.value == "EASY"

    def test_medium_complexity(self):
        """Moderate flags should be MEDIUM."""
        meds = [Medication(name=f"med{i}") for i in range(8)]
        flags = [
            ClinicalFlag(
                severity=Severity.MEDIUM,
                category=FlagCategory.BEERS_CRITERIA,
                finding="test",
                significance="test",
                recommendation="test"
            )
            for _ in range(3)
        ]

        score, level = calculate_complexity_score(flags, meds)

        assert level.value == "MEDIUM"

    def test_hard_complexity(self):
        """Many high-severity flags should be HARD."""
        meds = [Medication(name=f"med{i}") for i in range(12)]
        meds.append(Medication(name="quetiapine"))  # antipsychotic
        meds.append(Medication(name="risperidone"))  # antipsychotic
        flags = [
            ClinicalFlag(
                severity=Severity.HIGH,
                category=FlagCategory.ANTIPSYCHOTIC,
                finding="test",
                significance="test",
                recommendation="test"
            )
            for _ in range(5)
        ]

        score, level = calculate_complexity_score(flags, meds)

        assert level.value == "HARD"


class TestFullAnalysis:
    """Integration tests for full analysis."""

    def test_hard_case_fixture(self):
        """Test complex case with multiple issues."""
        patient = Patient(
            name="Test Patient",
            age=82,
            diagnoses=["dementia", "hypertension", "diabetes"],
            allergies=["penicillin"]
        )
        meds = [
            Medication(name="quetiapine", dose="100mg", frequency="twice daily"),
            Medication(name="lorazepam", dose="1mg", frequency="at bedtime"),
            Medication(name="oxycodone", dose="5mg", frequency="every 6 hours", is_prn=True),
            Medication(name="diphenhydramine", dose="25mg", frequency="at bedtime"),
            Medication(name="warfarin", dose="5mg", frequency="daily"),
            Medication(name="metformin", dose="1000mg", frequency="twice daily"),
        ]
        labs = []  # No labs to trigger monitoring flags

        parsed = ParsedChart(patient=patient, medications=meds, labs=labs)
        analysis = analyze_medications(parsed)

        # Should have multiple HIGH flags
        high_flags = [f for f in analysis.flags if f.severity == Severity.HIGH]
        assert len(high_flags) >= 3

        # Should be HARD complexity
        assert analysis.complexity_level.value == "HARD"

        # Should detect opioid + benzo
        opioid_benzo_flags = [
            f for f in analysis.flags
            if "opioid and benzodiazepine" in f.finding.lower()
        ]
        assert len(opioid_benzo_flags) >= 1

        # Should flag missing bowel regimen
        bowel_flags = [f for f in analysis.flags if "bowel regimen" in f.finding.lower()]
        assert len(bowel_flags) >= 1

        # Should have multiple Beers flags
        assert analysis.beers_count >= 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
