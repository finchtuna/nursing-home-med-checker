"""Unit tests for the Diana-style report generator."""

import pytest
from datetime import date, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import (
    ParsedChart, Patient, Medication, LabResult,
    ClinicalFlag, AnalysisResult, Severity, FlagCategory,
    RecommendationRouting, ComplexityLevel,
)
from note_generator import generate_diana_style_report, generate_flags_only_report
from analyzer import analyze_medications


class TestDianaStyleReportStructure:
    """Test overall structure of Diana-style report."""

    def _make_parsed(self):
        patient = Patient(
            name="Smith, Margaret",
            age=82,
            sex="Female",
            dob=date(1942, 3, 15),
            room="204-B",
            care_center="Memory Care Unit",
            attending_physician="Dr. Johnson",
            psychiatrist="Dr. Patel",
            diagnoses=["Alzheimer's dementia", "Depression", "Hypertension"],
            allergies=["Penicillin (rash)"],
        )
        meds = [
            Medication(name="quetiapine", dose="100mg", frequency="twice daily",
                       start_date=date.today() - timedelta(days=200)),
            Medication(name="sertraline", dose="100mg", frequency="daily"),
            Medication(name="warfarin", dose="5mg", frequency="daily"),
            Medication(name="aspirin", dose="81mg", frequency="daily"),
            Medication(name="omeprazole", dose="20mg", frequency="daily",
                       start_date=date.today() - timedelta(days=90)),
        ]
        return ParsedChart(patient=patient, medications=meds, labs=[])

    def test_report_contains_cover_summary(self):
        parsed = self._make_parsed()
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "CONSULTANT PHARMACIST MEDICATION REGIMEN REVIEW" in report
        assert "Smith, Margaret" in report
        assert "204-B" in report
        assert "Memory Care Unit" in report
        assert "Dr. Johnson" in report

    def test_report_contains_finding_summary(self):
        parsed = self._make_parsed()
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "FINDING SUMMARY" in report
        assert "HIGH Priority:" in report
        assert "MEDIUM Priority:" in report
        assert "LOW Priority:" in report
        assert "Total Findings:" in report

    def test_report_contains_routing_summary(self):
        parsed = self._make_parsed()
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "RECOMMENDATION ROUTING" in report
        assert "Attending Physician:" in report
        assert "Psychiatrist:" in report
        assert "Nursing:" in report

    def test_report_contains_physician_notes(self):
        parsed = self._make_parsed()
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "PHYSICIAN RECOMMENDATIONS" in report
        assert "Note To Attending Physician/Prescriber" in report or "Note To Psychiatrist/Prescriber" in report

    def test_report_contains_response_blocks(self):
        parsed = self._make_parsed()
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "PHYSICIAN RESPONSE:" in report
        assert "AGREE with recommendation" in report
        assert "DISAGREE" in report
        assert "Physician Signature:" in report

    def test_report_contains_pharmacist_signature(self):
        parsed = self._make_parsed()
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis, pharmacist_name="Diana Lu")

        assert "Diana Lu" in report
        assert "Consultant Pharmacist" in report
        assert "Pharmacist Signature:" in report

    def test_report_contains_disclaimer(self):
        parsed = self._make_parsed()
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "Final prescribing decisions" in report
        assert "attending physician" in report


class TestDianaStyleNursingSection:
    """Test nursing notes section."""

    def test_nursing_section_present_when_nursing_flags(self):
        patient = Patient(name="Test Patient")
        meds = [
            Medication(name="warfarin", dose="5mg"),
            Medication(name="fluticasone-salmeterol", dose="250/50"),
        ]
        parsed = ParsedChart(patient=patient, medications=meds, labs=[])
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "NURSING RECOMMENDATIONS" in report
        assert "Nurse Acknowledgment:" in report


class TestDianaStyleAntibioticSection:
    """Test antibiotic stewardship section."""

    def test_antibiotic_section_present_when_abx_flags(self):
        patient = Patient(name="Test Patient")
        meds = [Medication(name="amoxicillin", dose="500mg", frequency="three times daily")]
        parsed = ParsedChart(patient=patient, medications=meds, labs=[])
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "ANTIBIOTIC STEWARDSHIP RECOMMENDATIONS" in report


class TestDianaStyleWithMinimalData:
    """Test report with minimal patient data."""

    def test_report_works_with_minimal_patient(self):
        patient = Patient()
        meds = [Medication(name="lisinopril", dose="10mg")]
        parsed = ParsedChart(patient=patient, medications=meds, labs=[])
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "CONSULTANT PHARMACIST MEDICATION REGIMEN REVIEW" in report
        assert "Unknown" in report  # Name defaults to Unknown

    def test_report_works_with_no_flags(self):
        patient = Patient(name="Simple Patient", age=55)
        meds = [Medication(name="lisinopril", dose="10mg")]
        labs = [LabResult(test_name="CMP", value=1.0, date=date.today()),
                LabResult(test_name="potassium", value=4.0, date=date.today())]
        parsed = ParsedChart(patient=patient, medications=meds, labs=labs)
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "CONSULTANT PHARMACIST MEDICATION REGIMEN REVIEW" in report
        assert "Pharmacist Signature:" in report


class TestDianaStyleCustomPharmacist:
    """Test pharmacist name customization."""

    def test_default_pharmacist_name(self):
        patient = Patient(name="Test")
        meds = [Medication(name="lisinopril", dose="10mg")]
        parsed = ParsedChart(patient=patient, medications=meds, labs=[])
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis)

        assert "Consultant Pharmacist, Consultant Pharmacist" in report

    def test_custom_pharmacist_name(self):
        patient = Patient(name="Test")
        meds = [Medication(name="lisinopril", dose="10mg")]
        parsed = ParsedChart(patient=patient, medications=meds, labs=[])
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis, pharmacist_name="Diana Lu, PharmD")

        assert "Diana Lu, PharmD" in report


class TestBackwardCompatibility:
    """Ensure existing report functions still work."""

    def test_flags_only_report_still_works(self):
        patient = Patient(name="Test Patient", age=82)
        meds = [
            Medication(name="quetiapine", dose="100mg"),
            Medication(name="warfarin", dose="5mg"),
        ]
        parsed = ParsedChart(patient=patient, medications=meds, labs=[])
        analysis = analyze_medications(parsed)
        report = generate_flags_only_report(parsed, analysis)

        assert "MEDICATION REGIMEN REVIEW - FLAGS REPORT" in report
        assert "Test Patient" in report


class TestDianaReportComplexCase:
    """Integration test with a complex clinical scenario."""

    def test_complex_case_produces_comprehensive_report(self):
        patient = Patient(
            name="Davis, Eleanor",
            age=88,
            sex="Female",
            dob=date(1937, 7, 22),
            room="312-A",
            care_center="Skilled Nursing",
            attending_physician="Dr. Williams",
            psychiatrist="Dr. Chen",
            diagnoses=["Alzheimer's dementia", "heart failure", "diabetes type 2",
                        "depression", "chronic pain", "seizure disorder"],
            allergies=["Penicillin (anaphylaxis)", "Sulfa (rash)"],
            admission_date=date.today() - timedelta(days=15),
            is_new_admission=True,
        )
        meds = [
            Medication(name="quetiapine", dose="100mg", frequency="twice daily",
                       start_date=date.today() - timedelta(days=200)),
            Medication(name="sertraline", dose="100mg", frequency="daily"),
            Medication(name="warfarin", dose="5mg", frequency="daily"),
            Medication(name="aspirin", dose="81mg", frequency="daily"),
            Medication(name="omeprazole", dose="20mg", frequency="daily",
                       start_date=date.today() - timedelta(days=90)),
            Medication(name="metformin", dose="500mg", frequency="twice daily"),
            Medication(name="oxycodone", dose="5mg", frequency="every 6 hours", is_prn=True,
                       indication="pain management"),
            Medication(name="fluticasone-salmeterol", dose="250/50", frequency="twice daily"),
            Medication(name="potassium chloride", dose="20mEq", frequency="daily"),
            Medication(name="amoxicillin", dose="500mg", frequency="three times daily"),
        ]
        labs = [LabResult(test_name="Sodium", value=140.0, date=date.today())]

        parsed = ParsedChart(patient=patient, medications=meds, labs=labs)
        analysis = analyze_medications(parsed)
        report = generate_diana_style_report(parsed, analysis, pharmacist_name="Diana Lu, PharmD, BCGP")

        # Should have all sections
        assert "CONSULTANT PHARMACIST MEDICATION REGIMEN REVIEW" in report
        assert "Davis, Eleanor" in report
        assert "312-A" in report
        assert "Dr. Williams" in report
        assert "FINDING SUMMARY" in report
        assert "RECOMMENDATION ROUTING" in report
        assert "PHYSICIAN RECOMMENDATIONS" in report
        assert "NURSING RECOMMENDATIONS" in report
        assert "ANTIBIOTIC STEWARDSHIP RECOMMENDATIONS" in report
        assert "Diana Lu, PharmD, BCGP" in report

        # Should have significant findings
        assert "HIGH Priority:" in report

        # Verify it's a substantial report
        assert len(report) > 2000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
