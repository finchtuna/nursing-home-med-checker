"""Narrative clinical note generation via Claude API."""

from models import ParsedChart, AnalysisResult, Severity, FlagCategory
from config import get_anthropic_client, NARRATIVE_MODEL


NOTE_GENERATION_PROMPT = """You are a clinical documentation assistant for a Long-Term Care (LTC) consultant pharmacist.

Generate a professional clinical narrative note based on the provided patient data and analysis results. The note should be suitable for inclusion in the patient's medical record and communication with the care team.

## NOTE STRUCTURE

Generate the note with these sections:

### 1. HEADER
- Date of review
- Patient identifier (use name if available, otherwise "Patient")
- Facility (if known)
- Consultant pharmacist medication regimen review

### 2. PATIENT SUMMARY
- Brief demographics (age, sex)
- Active diagnoses
- Allergies
- Total medication count

### 3. MEDICATION REGIMEN OVERVIEW
- Summary of current medications by category
- Note any high-risk medication categories present (antipsychotics, opioids, benzodiazepines, anticoagulants)

### 4. CLINICAL FINDINGS
For each finding, organize by severity (HIGH priority first, then MEDIUM, then LOW):
- State the finding clearly
- Explain clinical significance
- Provide specific recommendation
- Note if prescriber action is needed

### 5. ANTIPSYCHOTIC REVIEW (if applicable)
- List all antipsychotics with doses
- GDR status/recommendations
- Black box warning acknowledgment
- Indication documentation status

### 6. LAB MONITORING STATUS
- Labs that are current
- Labs that are due or overdue
- Specific recommendations for lab orders

### 7. FALL RISK ASSESSMENT
- Count of fall-risk medications
- Specific medications contributing to fall risk
- Recommendations for mitigation

### 8. RECOMMENDATIONS SUMMARY
- Numbered list of actionable recommendations
- Prioritize by clinical urgency
- Include specific medications and suggested actions

### 9. COMPLEXITY ASSESSMENT
- Complexity score and level
- Justification for complexity rating

### 10. DISCLAIMER
Include: "This medication regimen review is intended to assist in optimizing pharmacotherapy. All recommendations should be evaluated in the context of the patient's complete clinical picture. Final prescribing decisions rest with the attending physician."

## FORMATTING GUIDELINES
- Use professional clinical language
- Be concise but thorough
- Use standard medical abbreviations appropriately
- Format for readability (headers, bullet points where appropriate)
- Do not include patient identifiers beyond what's provided
- Date all recommendations

## OUTPUT
Return ONLY the clinical note text, properly formatted. Do not include any JSON or metadata."""


def generate_clinical_note(parsed: ParsedChart, analysis: AnalysisResult) -> str:
    """Generate narrative clinical note using Claude API."""
    client = get_anthropic_client()

    # Build context for the prompt
    context = _build_context(parsed, analysis)

    try:
        response = client.messages.create(
            model=NARRATIVE_MODEL,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"{NOTE_GENERATION_PROMPT}\n\n---\n\n{context}"
                }
            ]
        )

        return response.content[0].text

    except Exception as e:
        return f"Error generating clinical note: {str(e)}"


def _build_context(parsed: ParsedChart, analysis: AnalysisResult) -> str:
    """Build context string for note generation."""
    lines = []

    # Patient information
    lines.append("## PATIENT INFORMATION")
    patient = parsed.patient
    if patient.name:
        lines.append(f"Name: {patient.name}")
    if patient.age:
        lines.append(f"Age: {patient.age}")
    if patient.sex:
        lines.append(f"Sex: {patient.sex}")
    if patient.diagnoses:
        lines.append(f"Diagnoses: {', '.join(patient.diagnoses)}")
    if patient.allergies:
        lines.append(f"Allergies: {', '.join(patient.allergies)}")
    lines.append("")

    # Medication list
    lines.append("## CURRENT MEDICATIONS")
    lines.append(f"Total count: {len(parsed.medications)}")
    lines.append("")
    for med in parsed.medications:
        med_line = f"- {med.name}"
        if med.dose:
            med_line += f" {med.dose}"
        if med.route:
            med_line += f" {med.route}"
        if med.frequency:
            med_line += f" {med.frequency}"
        if med.is_prn:
            med_line += " (PRN)"
        if med.indication:
            med_line += f" [for: {med.indication}]"
        lines.append(med_line)
    lines.append("")

    # Labs
    if parsed.labs:
        lines.append("## LABORATORY RESULTS")
        for lab in parsed.labs:
            lab_line = f"- {lab.test_name}"
            if lab.value is not None:
                lab_line += f": {lab.value}"
            elif lab.value_text:
                lab_line += f": {lab.value_text}"
            if lab.unit:
                lab_line += f" {lab.unit}"
            if lab.date:
                lab_line += f" ({lab.date})"
            if lab.flag:
                lab_line += f" [{lab.flag}]"
            lines.append(lab_line)
        lines.append("")

    # Analysis summary
    lines.append("## ANALYSIS SUMMARY")
    lines.append(f"Complexity Score: {analysis.complexity_score}")
    lines.append(f"Complexity Level: {analysis.complexity_level.value}")
    lines.append(f"Total Medications: {analysis.total_medications}")
    lines.append(f"Fall Risk Medications: {analysis.fall_risk_count}")
    lines.append(f"CNS Depressants: {analysis.cns_depressant_count}")
    lines.append(f"Anticholinergic Medications: {analysis.anticholinergic_count}")
    lines.append(f"Controlled Substances: {analysis.controlled_substance_count}")
    lines.append(f"Antipsychotics: {analysis.antipsychotic_count}")
    lines.append(f"Beers Criteria Medications: {analysis.beers_count}")
    lines.append("")

    # GDR tracking
    if analysis.antipsychotics_needing_gdr:
        lines.append("## GDR STATUS")
        lines.append("Antipsychotics potentially needing GDR:")
        for ap in analysis.antipsychotics_needing_gdr:
            lines.append(f"- {ap}")
        lines.append("")

    # Lab monitoring
    if analysis.labs_overdue or analysis.labs_due:
        lines.append("## LAB MONITORING STATUS")
        if analysis.labs_overdue:
            lines.append(f"Overdue: {', '.join(analysis.labs_overdue)}")
        if analysis.labs_due:
            lines.append(f"Due soon: {', '.join(analysis.labs_due)}")
        lines.append("")

    # Clinical flags
    lines.append("## CLINICAL FLAGS")
    lines.append("")

    # Sort by severity
    severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFO: 3}
    sorted_flags = sorted(analysis.flags, key=lambda f: severity_order[f.severity])

    for flag in sorted_flags:
        lines.append(f"### [{flag.severity.value}] {flag.category.value}")
        lines.append(f"**Finding:** {flag.finding}")
        lines.append(f"**Significance:** {flag.significance}")
        lines.append(f"**Recommendation:** {flag.recommendation}")
        if flag.prescriber_action_needed:
            lines.append("**Prescriber action needed:** Yes")
        if flag.medications_involved:
            lines.append(f"**Medications:** {', '.join(flag.medications_involved)}")
        lines.append("")

    # Parsing notes
    if parsed.parsing_notes:
        lines.append("## PARSING NOTES")
        for note in parsed.parsing_notes:
            lines.append(f"- {note}")
        lines.append(f"Parsing confidence: {parsed.parsing_confidence}")

    return "\n".join(lines)


def generate_flags_only_report(parsed: ParsedChart, analysis: AnalysisResult) -> str:
    """Generate a concise flags-only report without narrative."""
    lines = []

    lines.append("=" * 60)
    lines.append("MEDICATION REGIMEN REVIEW - FLAGS REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Patient summary
    patient = parsed.patient
    if patient.name:
        lines.append(f"Patient: {patient.name}")
    if patient.age:
        lines.append(f"Age: {patient.age}")
    lines.append(f"Total Medications: {len(parsed.medications)}")
    lines.append(f"Complexity: {analysis.complexity_level.value} (Score: {analysis.complexity_score})")
    lines.append("")

    # Summary counts
    lines.append("-" * 40)
    lines.append("SUMMARY COUNTS")
    lines.append("-" * 40)
    lines.append(f"Fall Risk Medications:    {analysis.fall_risk_count}")
    lines.append(f"CNS Depressants:          {analysis.cns_depressant_count}")
    lines.append(f"Anticholinergics:         {analysis.anticholinergic_count}")
    lines.append(f"Controlled Substances:    {analysis.controlled_substance_count}")
    lines.append(f"Antipsychotics:           {analysis.antipsychotic_count}")
    lines.append(f"Beers Criteria:           {analysis.beers_count}")
    lines.append("")

    # Flags by severity
    severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2, Severity.INFO: 3}
    sorted_flags = sorted(analysis.flags, key=lambda f: severity_order[f.severity])

    high_flags = [f for f in sorted_flags if f.severity == Severity.HIGH]
    medium_flags = [f for f in sorted_flags if f.severity == Severity.MEDIUM]
    low_flags = [f for f in sorted_flags if f.severity == Severity.LOW]
    info_flags = [f for f in sorted_flags if f.severity == Severity.INFO]

    if high_flags:
        lines.append("-" * 40)
        lines.append("HIGH PRIORITY FLAGS")
        lines.append("-" * 40)
        for flag in high_flags:
            lines.append(f"\n[{flag.category.value}]")
            lines.append(f"  Finding: {flag.finding}")
            lines.append(f"  Action: {flag.recommendation}")
            if flag.medications_involved:
                lines.append(f"  Meds: {', '.join(flag.medications_involved)}")
        lines.append("")

    if medium_flags:
        lines.append("-" * 40)
        lines.append("MEDIUM PRIORITY FLAGS")
        lines.append("-" * 40)
        for flag in medium_flags:
            lines.append(f"\n[{flag.category.value}]")
            lines.append(f"  Finding: {flag.finding}")
            lines.append(f"  Action: {flag.recommendation}")
        lines.append("")

    if low_flags:
        lines.append("-" * 40)
        lines.append("LOW PRIORITY FLAGS")
        lines.append("-" * 40)
        for flag in low_flags:
            lines.append(f"\n[{flag.category.value}]")
            lines.append(f"  Finding: {flag.finding}")
        lines.append("")

    if info_flags:
        lines.append("-" * 40)
        lines.append("INFORMATIONAL")
        lines.append("-" * 40)
        for flag in info_flags:
            lines.append(f"  - {flag.finding}")
        lines.append("")

    # Lab monitoring
    if analysis.labs_overdue:
        lines.append("-" * 40)
        lines.append("LABS OVERDUE")
        lines.append("-" * 40)
        for lab in analysis.labs_overdue:
            lines.append(f"  - {lab}")
        lines.append("")

    # GDR tracking
    if analysis.antipsychotics_needing_gdr:
        lines.append("-" * 40)
        lines.append("GDR REVIEW NEEDED")
        lines.append("-" * 40)
        for ap in analysis.antipsychotics_needing_gdr:
            lines.append(f"  - {ap}")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)
