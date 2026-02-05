"""Unit tests for the 25 Diana-style clinical rules."""

import pytest
from datetime import date, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import (
    ParsedChart, Patient, Medication, LabResult,
    ClinicalFlag, Severity, FlagCategory, RecommendationRouting,
)
from analyzer import (
    check_ppi_long_term,
    check_metformin_renal_monitoring,
    check_megace_high_risk,
    check_fleet_enema_risk,
    check_anticoagulant_monitoring,
    check_aspirin_anticoagulant,
    check_bupropion_seizure,
    check_digoxin_diltiazem,
    check_solifenacin_opioid,
    check_tamsulosin_timing,
    check_steroid_inhaler_rinse,
    check_duplicate_prn,
    check_unused_prn,
    check_allergy_conflict,
    check_hold_parameter_mismatch,
    check_supplement_with_normal_labs,
    check_vague_pain_diagnosis,
    check_topical_steroid_duration,
    check_naloxone_without_opioid,
    check_antibiotic_no_stop_date,
    check_potassium_administration,
    check_metoprolol_formulation,
    check_suzetrigine_duration,
    check_gdr_assessment,
    check_new_admission_psychotropic,
)


class TestPPILongTerm:
    """Rule 1: PPI long-term use."""

    def test_ppi_over_8_weeks_flags(self):
        meds = [Medication(name="omeprazole", dose="20mg", start_date=date.today() - timedelta(days=60))]
        flags = check_ppi_long_term(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.MEDIUM
        assert flags[0].category == FlagCategory.PPI_LONG_TERM
        assert flags[0].diana_narrative is not None

    def test_ppi_under_8_weeks_no_flag(self):
        meds = [Medication(name="pantoprazole", dose="40mg", start_date=date.today() - timedelta(days=30))]
        flags = check_ppi_long_term(meds)
        assert len(flags) == 0

    def test_ppi_no_start_date_no_flag(self):
        meds = [Medication(name="omeprazole", dose="20mg")]
        flags = check_ppi_long_term(meds)
        assert len(flags) == 0


class TestMetforminRenalMonitoring:
    """Rule 2: Metformin renal monitoring."""

    def test_metformin_without_bmp_flags_high(self):
        meds = [Medication(name="metformin", dose="500mg")]
        labs = []
        flags = check_metformin_renal_monitoring(meds, labs)
        bmp_flags = [f for f in flags if "renal" in f.finding.lower()]
        assert len(bmp_flags) >= 1
        assert bmp_flags[0].severity == Severity.HIGH

    def test_metformin_without_a1c_flags_medium(self):
        meds = [Medication(name="metformin", dose="500mg")]
        labs = [LabResult(test_name="BMP", value=1.0, date=date.today())]
        flags = check_metformin_renal_monitoring(meds, labs)
        a1c_flags = [f for f in flags if "a1c" in f.finding.lower()]
        assert len(a1c_flags) >= 1
        assert a1c_flags[0].severity == Severity.MEDIUM

    def test_metformin_with_all_labs_no_flag(self):
        meds = [Medication(name="metformin", dose="500mg")]
        labs = [
            LabResult(test_name="BMP", value=1.0, date=date.today()),
            LabResult(test_name="HbA1c", value=6.5, date=date.today()),
        ]
        flags = check_metformin_renal_monitoring(meds, labs)
        assert len(flags) == 0

    def test_no_metformin_no_flag(self):
        meds = [Medication(name="lisinopril", dose="10mg")]
        labs = []
        flags = check_metformin_renal_monitoring(meds, labs)
        assert len(flags) == 0


class TestMegaceHighRisk:
    """Rule 3: Megace high-risk."""

    def test_megestrol_flags_high(self):
        meds = [Medication(name="megestrol", dose="400mg")]
        flags = check_megace_high_risk(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.HIGH
        assert flags[0].category == FlagCategory.HIGH_RISK_MEDICATION
        assert flags[0].diana_narrative is not None

    def test_no_megestrol_no_flag(self):
        meds = [Medication(name="omeprazole", dose="20mg")]
        flags = check_megace_high_risk(meds)
        assert len(flags) == 0


class TestFleetEnemaRisk:
    """Rule 4: Fleet enema risk."""

    def test_fleet_with_heart_failure_flags_high(self):
        meds = [Medication(name="sodium phosphate enema", dose="1 enema")]
        diagnoses = ["heart failure", "hypertension"]
        flags = check_fleet_enema_risk(meds, diagnoses)
        assert len(flags) == 1
        assert flags[0].severity == Severity.HIGH

    def test_fleet_without_risk_no_flag(self):
        meds = [Medication(name="sodium phosphate enema", dose="1 enema")]
        diagnoses = ["hypertension", "diabetes"]
        flags = check_fleet_enema_risk(meds, diagnoses)
        assert len(flags) == 0

    def test_fleet_with_ckd_flags(self):
        meds = [Medication(name="sodium phosphate enema", dose="1 enema")]
        diagnoses = ["ckd stage 3", "diabetes"]
        flags = check_fleet_enema_risk(meds, diagnoses)
        assert len(flags) == 1


class TestAnticoagulantMonitoring:
    """Rule 5: Anticoagulant monitoring."""

    def test_anticoagulant_nursing_note(self):
        meds = [Medication(name="warfarin", dose="5mg")]
        flags = check_anticoagulant_monitoring(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.LOW
        assert flags[0].routing == RecommendationRouting.NURSING

    def test_no_anticoagulant_no_flag(self):
        meds = [Medication(name="lisinopril", dose="10mg")]
        flags = check_anticoagulant_monitoring(meds)
        assert len(flags) == 0


class TestAspirinAnticoagulant:
    """Rule 6: ASA + anticoagulant."""

    def test_aspirin_plus_warfarin_flags_high(self):
        meds = [
            Medication(name="aspirin", dose="81mg"),
            Medication(name="warfarin", dose="5mg"),
        ]
        flags = check_aspirin_anticoagulant(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.HIGH
        assert flags[0].category == FlagCategory.ASPIRIN_ANTICOAGULANT

    def test_aspirin_plus_apixaban_flags_high(self):
        meds = [
            Medication(name="aspirin", dose="81mg"),
            Medication(name="apixaban", dose="5mg"),
        ]
        flags = check_aspirin_anticoagulant(meds)
        assert len(flags) == 1

    def test_aspirin_alone_no_flag(self):
        meds = [Medication(name="aspirin", dose="81mg")]
        flags = check_aspirin_anticoagulant(meds)
        assert len(flags) == 0


class TestBupropionSeizure:
    """Rule 7: Bupropion + seizure disorder."""

    def test_bupropion_with_seizure_flags_high(self):
        meds = [Medication(name="bupropion", dose="150mg")]
        diagnoses = ["seizure disorder", "depression"]
        flags = check_bupropion_seizure(meds, diagnoses)
        assert len(flags) == 1
        assert flags[0].severity == Severity.HIGH
        assert flags[0].category == FlagCategory.SEIZURE_CONTRAINDICATION

    def test_bupropion_without_seizure_no_flag(self):
        meds = [Medication(name="bupropion", dose="150mg")]
        diagnoses = ["depression", "anxiety"]
        flags = check_bupropion_seizure(meds, diagnoses)
        assert len(flags) == 0


class TestDigoxinDiltiazem:
    """Rule 8: Digoxin + diltiazem."""

    def test_digoxin_diltiazem_flags_high(self):
        meds = [
            Medication(name="digoxin", dose="0.125mg"),
            Medication(name="diltiazem", dose="120mg"),
        ]
        flags = check_digoxin_diltiazem(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.HIGH
        assert flags[0].category == FlagCategory.DIGOXIN_INTERACTION

    def test_digoxin_alone_no_flag(self):
        meds = [Medication(name="digoxin", dose="0.125mg")]
        flags = check_digoxin_diltiazem(meds)
        assert len(flags) == 0


class TestSolifenacinOpioid:
    """Rule 9: Solifenacin + opioid."""

    def test_solifenacin_with_opioid_flags(self):
        meds = [
            Medication(name="solifenacin", dose="5mg"),
            Medication(name="oxycodone", dose="5mg"),
        ]
        flags = check_solifenacin_opioid(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.MEDIUM
        assert flags[0].category == FlagCategory.URINARY_RETENTION_RISK

    def test_solifenacin_alone_no_flag(self):
        meds = [Medication(name="solifenacin", dose="5mg")]
        flags = check_solifenacin_opioid(meds)
        assert len(flags) == 0


class TestTamsulosinTiming:
    """Rule 10: Tamsulosin AM timing."""

    def test_tamsulosin_am_flags(self):
        meds = [Medication(name="tamsulosin", dose="0.4mg", frequency="every morning")]
        flags = check_tamsulosin_timing(meds)
        assert len(flags) == 1
        assert flags[0].routing == RecommendationRouting.NURSING

    def test_tamsulosin_bedtime_no_flag(self):
        meds = [Medication(name="tamsulosin", dose="0.4mg", frequency="at bedtime")]
        flags = check_tamsulosin_timing(meds)
        assert len(flags) == 0

    def test_tamsulosin_am_admin_time_flags(self):
        meds = [Medication(name="tamsulosin", dose="0.4mg", frequency="daily", administration_time="AM")]
        flags = check_tamsulosin_timing(meds)
        assert len(flags) == 1


class TestSteroidInhalerRinse:
    """Rule 11: Steroid inhaler rinse."""

    def test_steroid_inhaler_flags(self):
        meds = [Medication(name="fluticasone-salmeterol", dose="250/50")]
        flags = check_steroid_inhaler_rinse(meds)
        assert len(flags) == 1
        assert flags[0].routing == RecommendationRouting.NURSING
        assert flags[0].category == FlagCategory.STEROID_INHALER_CARE

    def test_no_steroid_inhaler_no_flag(self):
        meds = [Medication(name="albuterol", dose="2 puffs")]
        flags = check_steroid_inhaler_rinse(meds)
        assert len(flags) == 0


class TestDuplicatePRN:
    """Rule 12: Duplicate PRN."""

    def test_duplicate_prn_same_indication_flags(self):
        meds = [
            Medication(name="oxycodone", dose="5mg", is_prn=True, indication="pain"),
            Medication(name="hydrocodone", dose="5mg", is_prn=True, indication="pain"),
        ]
        flags = check_duplicate_prn(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.MEDIUM
        assert flags[0].category == FlagCategory.DUPLICATE_PRN

    def test_prn_different_indications_no_flag(self):
        meds = [
            Medication(name="oxycodone", dose="5mg", is_prn=True, indication="pain"),
            Medication(name="lorazepam", dose="0.5mg", is_prn=True, indication="anxiety"),
        ]
        flags = check_duplicate_prn(meds)
        assert len(flags) == 0


class TestUnusedPRN:
    """Rule 13: Unused PRN."""

    def test_prn_unused_over_90_days_flags(self):
        meds = [Medication(name="lorazepam", dose="0.5mg", is_prn=True,
                           last_used_date=date.today() - timedelta(days=100))]
        flags = check_unused_prn(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.LOW
        assert flags[0].category == FlagCategory.UNUSED_PRN

    def test_prn_recently_used_no_flag(self):
        meds = [Medication(name="lorazepam", dose="0.5mg", is_prn=True,
                           last_used_date=date.today() - timedelta(days=30))]
        flags = check_unused_prn(meds)
        assert len(flags) == 0


class TestAllergyConflict:
    """Rule 14: Allergy conflict."""

    def test_direct_allergy_match_flags(self):
        meds = [Medication(name="aspirin", dose="81mg")]
        allergies = ["aspirin (gi bleed)"]
        flags = check_allergy_conflict(meds, allergies)
        assert len(flags) >= 1
        assert flags[0].severity == Severity.HIGH
        assert flags[0].category == FlagCategory.ALLERGY_CONFLICT

    def test_cross_reactivity_flags(self):
        meds = [Medication(name="amoxicillin", dose="500mg")]
        allergies = ["penicillin"]
        flags = check_allergy_conflict(meds, allergies)
        assert len(flags) >= 1

    def test_no_allergy_match_no_flag(self):
        meds = [Medication(name="lisinopril", dose="10mg")]
        allergies = ["penicillin"]
        flags = check_allergy_conflict(meds, allergies)
        assert len(flags) == 0


class TestHoldParameterMismatch:
    """Rule 15: Hold parameter mismatch."""

    def test_different_hold_params_flags(self):
        meds = [
            Medication(name="lisinopril", dose="10mg", hold_parameters="hold for SBP <100"),
            Medication(name="amlodipine", dose="5mg", hold_parameters="hold for SBP <90"),
        ]
        flags = check_hold_parameter_mismatch(meds)
        assert len(flags) == 1
        assert flags[0].category == FlagCategory.HOLD_PARAMETER_MISMATCH

    def test_same_hold_params_no_flag(self):
        meds = [
            Medication(name="lisinopril", dose="10mg", hold_parameters="hold for SBP <100"),
            Medication(name="amlodipine", dose="5mg", hold_parameters="hold for SBP <100"),
        ]
        flags = check_hold_parameter_mismatch(meds)
        assert len(flags) == 0


class TestSupplementNormalLabs:
    """Rule 16: Supplement with normal labs."""

    def test_sodium_supplement_normal_na_flags(self):
        meds = [Medication(name="sodium chloride", dose="1g")]
        labs = [LabResult(test_name="Sodium", value=140.0, flag=None)]
        flags = check_supplement_with_normal_labs(meds, labs)
        assert len(flags) == 1
        assert flags[0].category == FlagCategory.SUPPLEMENT_UNNECESSARY

    def test_sodium_supplement_low_na_no_flag(self):
        meds = [Medication(name="sodium chloride", dose="1g")]
        labs = [LabResult(test_name="Sodium", value=128.0, flag="L")]
        flags = check_supplement_with_normal_labs(meds, labs)
        assert len(flags) == 0


class TestVaguePainDiagnosis:
    """Rule 17: Vague pain diagnosis."""

    def test_opioid_with_vague_indication_flags(self):
        meds = [Medication(name="oxycodone", dose="5mg", indication="pain management")]
        diagnoses = ["chronic pain"]
        flags = check_vague_pain_diagnosis(meds, diagnoses)
        assert len(flags) == 1
        assert flags[0].category == FlagCategory.VAGUE_DIAGNOSIS

    def test_opioid_with_specific_indication_no_flag(self):
        meds = [Medication(name="oxycodone", dose="5mg", indication="osteoarthritis of left knee")]
        diagnoses = ["osteoarthritis"]
        flags = check_vague_pain_diagnosis(meds, diagnoses)
        assert len(flags) == 0


class TestTopicalSteroidDuration:
    """Rule 18: Topical steroid duration."""

    def test_topical_steroid_over_30_days_flags(self):
        meds = [Medication(name="triamcinolone topical", dose="0.1%",
                           start_date=date.today() - timedelta(days=45))]
        flags = check_topical_steroid_duration(meds)
        assert len(flags) == 1
        assert flags[0].category == FlagCategory.TOPICAL_STEROID_DURATION

    def test_topical_steroid_under_30_days_no_flag(self):
        meds = [Medication(name="triamcinolone topical", dose="0.1%",
                           start_date=date.today() - timedelta(days=15))]
        flags = check_topical_steroid_duration(meds)
        assert len(flags) == 0


class TestNaloxoneWithoutOpioid:
    """Rule 19: Naloxone without opioid."""

    def test_naloxone_without_opioid_flags(self):
        meds = [Medication(name="naloxone", dose="4mg")]
        flags = check_naloxone_without_opioid(meds)
        assert len(flags) == 1
        assert flags[0].category == FlagCategory.NALOXONE_WITHOUT_OPIOID

    def test_naloxone_with_opioid_no_flag(self):
        meds = [
            Medication(name="naloxone", dose="4mg"),
            Medication(name="oxycodone", dose="5mg"),
        ]
        flags = check_naloxone_without_opioid(meds)
        assert len(flags) == 0


class TestAntibioticNoStopDate:
    """Rule 20: Antibiotic no stop date."""

    def test_antibiotic_no_stop_date_flags(self):
        meds = [Medication(name="amoxicillin", dose="500mg")]
        flags = check_antibiotic_no_stop_date(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.MEDIUM
        assert flags[0].routing == RecommendationRouting.ANTIBIOTIC_STEWARDSHIP

    def test_antibiotic_with_stop_date_no_flag(self):
        meds = [Medication(name="amoxicillin", dose="500mg",
                           stop_date=date.today() + timedelta(days=7))]
        flags = check_antibiotic_no_stop_date(meds)
        assert len(flags) == 0

    def test_antibiotic_with_duration_days_no_flag(self):
        """Antibiotic with duration_days set should NOT flag."""
        meds = [Medication(name="meropenem", dose="500mg", duration_days=14)]
        flags = check_antibiotic_no_stop_date(meds)
        assert len(flags) == 0

    def test_antibiotic_no_stop_date_no_duration_flags(self):
        """Antibiotic with neither stop_date nor duration_days should flag."""
        meds = [Medication(name="meropenem", dose="500mg")]
        flags = check_antibiotic_no_stop_date(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.MEDIUM

    def test_non_antibiotic_no_flag(self):
        meds = [Medication(name="lisinopril", dose="10mg")]
        flags = check_antibiotic_no_stop_date(meds)
        assert len(flags) == 0


class TestPotassiumAdministration:
    """Rule 21: Potassium administration."""

    def test_potassium_chloride_flags_nursing(self):
        meds = [Medication(name="potassium chloride", dose="20mEq")]
        flags = check_potassium_administration(meds)
        assert len(flags) == 1
        assert flags[0].routing == RecommendationRouting.NURSING

    def test_no_potassium_no_flag(self):
        meds = [Medication(name="lisinopril", dose="10mg")]
        flags = check_potassium_administration(meds)
        assert len(flags) == 0


class TestMetoprololFormulation:
    """Rule 22: Metoprolol formulation mismatch."""

    def test_succinate_bid_flags(self):
        meds = [Medication(name="metoprolol succinate", dose="50mg", frequency="twice daily")]
        flags = check_metoprolol_formulation(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.MEDIUM
        assert flags[0].category == FlagCategory.FORMULATION_MISMATCH

    def test_tartrate_daily_flags(self):
        meds = [Medication(name="metoprolol tartrate", dose="50mg", frequency="daily")]
        flags = check_metoprolol_formulation(meds)
        assert len(flags) == 1

    def test_succinate_daily_no_flag(self):
        meds = [Medication(name="metoprolol succinate", dose="50mg", frequency="daily")]
        flags = check_metoprolol_formulation(meds)
        assert len(flags) == 0


class TestSuzetrigineDuration:
    """Rule 23: Suzetrigine duration."""

    def test_suzetrigine_over_14_days_flags(self):
        meds = [Medication(name="suzetrigine", dose="50mg",
                           start_date=date.today() - timedelta(days=20))]
        flags = check_suzetrigine_duration(meds)
        assert len(flags) == 1
        assert flags[0].severity == Severity.MEDIUM
        assert flags[0].category == FlagCategory.SUZETRIGINE_DURATION

    def test_suzetrigine_under_14_days_no_flag(self):
        meds = [Medication(name="suzetrigine", dose="50mg",
                           start_date=date.today() - timedelta(days=10))]
        flags = check_suzetrigine_duration(meds)
        assert len(flags) == 0


class TestGDRAssessment:
    """Rule 24: GDR assessment for psychotropics."""

    def test_antipsychotic_over_180_days_flags_psychiatrist(self):
        meds = [Medication(name="quetiapine", dose="100mg",
                           start_date=date.today() - timedelta(days=200))]
        flags = check_gdr_assessment(meds)
        assert len(flags) >= 1
        gdr_flags = [f for f in flags if f.category == FlagCategory.GDR_ASSESSMENT]
        assert len(gdr_flags) >= 1
        assert gdr_flags[0].routing == RecommendationRouting.MD_PSYCHIATRIST

    def test_antipsychotic_under_180_days_no_gdr_flag(self):
        meds = [Medication(name="quetiapine", dose="100mg",
                           start_date=date.today() - timedelta(days=100))]
        flags = check_gdr_assessment(meds)
        gdr_flags = [f for f in flags if f.category == FlagCategory.GDR_ASSESSMENT]
        assert len(gdr_flags) == 0


class TestNewAdmissionPsychotropic:
    """Rule 25: New admission psychotropic review."""

    def test_new_admission_with_psychotropic_flags(self):
        patient = Patient(
            name="Test Patient",
            admission_date=date.today() - timedelta(days=10),
            is_new_admission=True,
        )
        meds = [Medication(name="sertraline", dose="100mg")]
        flags = check_new_admission_psychotropic(meds, patient)
        assert len(flags) == 1
        assert flags[0].severity == Severity.MEDIUM
        assert flags[0].routing == RecommendationRouting.MD_PSYCHIATRIST

    def test_old_admission_no_flag(self):
        patient = Patient(
            name="Test Patient",
            admission_date=date.today() - timedelta(days=60),
            is_new_admission=False,
        )
        meds = [Medication(name="sertraline", dose="100mg")]
        flags = check_new_admission_psychotropic(meds, patient)
        assert len(flags) == 0

    def test_new_admission_no_psychotropic_no_flag(self):
        patient = Patient(
            name="Test Patient",
            admission_date=date.today() - timedelta(days=10),
            is_new_admission=True,
        )
        meds = [Medication(name="lisinopril", dose="10mg")]
        flags = check_new_admission_psychotropic(meds, patient)
        assert len(flags) == 0


class TestDianaRulesRouting:
    """Test that routing is correctly set for Diana-style rules."""

    def test_nursing_routes(self):
        """Nursing-routed rules should have NURSING routing."""
        # Anticoagulant monitoring
        meds = [Medication(name="warfarin", dose="5mg")]
        flags = check_anticoagulant_monitoring(meds)
        assert all(f.routing == RecommendationRouting.NURSING for f in flags)

        # Steroid inhaler
        meds = [Medication(name="fluticasone-salmeterol", dose="250/50")]
        flags = check_steroid_inhaler_rinse(meds)
        assert all(f.routing == RecommendationRouting.NURSING for f in flags)

        # Potassium admin
        meds = [Medication(name="potassium chloride", dose="20mEq")]
        flags = check_potassium_administration(meds)
        assert all(f.routing == RecommendationRouting.NURSING for f in flags)

    def test_antibiotic_stewardship_route(self):
        """Antibiotic stewardship rules should have ANTIBIOTIC_STEWARDSHIP routing."""
        meds = [Medication(name="amoxicillin", dose="500mg")]
        flags = check_antibiotic_no_stop_date(meds)
        assert all(f.routing == RecommendationRouting.ANTIBIOTIC_STEWARDSHIP for f in flags)

    def test_psychiatrist_routes(self):
        """Psychiatrist-routed rules should have MD_PSYCHIATRIST routing."""
        patient = Patient(
            name="Test",
            admission_date=date.today() - timedelta(days=5),
            is_new_admission=True,
        )
        meds = [Medication(name="quetiapine", dose="100mg")]
        flags = check_new_admission_psychotropic(meds, patient)
        assert all(f.routing == RecommendationRouting.MD_PSYCHIATRIST for f in flags)


class TestDianaNarratives:
    """Test that diana_narrative is populated for all Diana-style rules."""

    def test_all_rules_have_narratives(self):
        """All Diana-style rules should produce flags with diana_narrative set."""
        # PPI
        meds = [Medication(name="omeprazole", start_date=date.today() - timedelta(days=60))]
        for f in check_ppi_long_term(meds):
            assert f.diana_narrative is not None and len(f.diana_narrative) > 50

        # Megace
        meds = [Medication(name="megestrol")]
        for f in check_megace_high_risk(meds):
            assert f.diana_narrative is not None

        # Aspirin + anticoagulant
        meds = [Medication(name="aspirin"), Medication(name="warfarin")]
        for f in check_aspirin_anticoagulant(meds):
            assert f.diana_narrative is not None

        # Digoxin + diltiazem
        meds = [Medication(name="digoxin"), Medication(name="diltiazem")]
        for f in check_digoxin_diltiazem(meds):
            assert f.diana_narrative is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
