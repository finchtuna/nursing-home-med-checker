"""Rule-based clinical analysis engine for LTC medication reconciliation."""

from datetime import date, timedelta
from models import (
    ParsedChart,
    Medication,
    LabResult,
    ClinicalFlag,
    AnalysisResult,
    Severity,
    FlagCategory,
    ComplexityLevel,
)
from drug_reference import (
    get_drug_info,
    normalize_drug_name,
    is_bowel_medication,
    is_opioid,
    ANTIPSYCHOTICS,
    BENZODIAZEPINES,
    OPIOIDS,
)
from config import LAB_MONITORING_INTERVALS, GDR_OVERDUE_DAYS


def analyze_medications(parsed: ParsedChart) -> AnalysisResult:
    """Run complete clinical analysis on parsed chart data."""
    flags: list[ClinicalFlag] = []
    meds = parsed.medications
    labs = parsed.labs
    patient = parsed.patient
    diagnoses = [d.lower() for d in patient.diagnoses]
    age = patient.age

    # Run all checks
    flags.extend(check_indication_verification(meds, diagnoses))
    flags.extend(check_lab_monitoring(meds, labs))
    flags.extend(check_drug_interactions(meds))
    flags.extend(check_beers_criteria(meds, age))
    flags.extend(check_antipsychotic_compliance(meds))
    flags.extend(check_controlled_substances(meds))
    flags.extend(check_fall_risk(meds))
    flags.extend(check_missing_prophylaxis(meds))

    # Calculate summary counts
    fall_risk_count = sum(1 for m in meds if _is_fall_risk_med(m.name))
    cns_depressant_count = sum(1 for m in meds if _is_cns_depressant(m.name))
    anticholinergic_count = sum(1 for m in meds if _is_anticholinergic(m.name))
    controlled_count = sum(1 for m in meds if _is_controlled(m.name))
    antipsychotic_count = sum(1 for m in meds if _is_antipsychotic(m.name))
    beers_count = sum(1 for m in meds if _is_beers_list(m.name))

    # Get antipsychotics needing GDR
    antipsychotics_needing_gdr = _get_antipsychotics_needing_gdr(meds)

    # Get labs due/overdue
    labs_due, labs_overdue = _get_lab_monitoring_status(meds, labs)

    # Calculate complexity
    complexity_score, complexity_level = calculate_complexity_score(flags, meds)

    return AnalysisResult(
        flags=flags,
        complexity_score=complexity_score,
        complexity_level=complexity_level,
        total_medications=len(meds),
        fall_risk_count=fall_risk_count,
        cns_depressant_count=cns_depressant_count,
        anticholinergic_count=anticholinergic_count,
        controlled_substance_count=controlled_count,
        antipsychotic_count=antipsychotic_count,
        beers_count=beers_count,
        antipsychotics_needing_gdr=antipsychotics_needing_gdr,
        labs_due=labs_due,
        labs_overdue=labs_overdue,
    )


def check_indication_verification(
    meds: list[Medication], diagnoses: list[str]
) -> list[ClinicalFlag]:
    """Flag medications without documented indications."""
    flags = []

    for med in meds:
        drug_info = get_drug_info(med.name)
        if not drug_info:
            continue

        has_indication = bool(med.indication)

        # Special handling for antipsychotics - stricter requirements
        if _is_antipsychotic(med.name):
            if not has_indication:
                flags.append(
                    ClinicalFlag(
                        severity=Severity.HIGH,
                        category=FlagCategory.INDICATION,
                        finding=f"Antipsychotic '{med.name}' lacks documented indication",
                        significance="CMS requires documented psychiatric diagnosis for antipsychotic use in LTC. "
                        "Missing indication may result in survey deficiency.",
                        recommendation="Verify and document specific psychiatric indication (e.g., schizophrenia, "
                        "bipolar disorder) or initiate gradual dose reduction if used for behavioral symptoms.",
                        prescriber_action_needed=True,
                        medications_involved=[med.name],
                    )
                )
            else:
                # Check if indication is appropriate
                inappropriate_indications = ["insomnia", "anxiety", "agitation", "behavior"]
                if any(ind in (med.indication or "").lower() for ind in inappropriate_indications):
                    flags.append(
                        ClinicalFlag(
                            severity=Severity.MEDIUM,
                            category=FlagCategory.INDICATION,
                            finding=f"Antipsychotic '{med.name}' has potentially inappropriate indication: {med.indication}",
                            significance="Antipsychotics should not be used for non-psychiatric indications. "
                            "CMS scrutinizes use for insomnia, anxiety, or behavioral management.",
                            recommendation="Consider non-pharmacological interventions. If antipsychotic required, "
                            "document specific target symptoms and treatment response.",
                            prescriber_action_needed=True,
                            medications_involved=[med.name],
                        )
                    )

        # Flag high-risk medications without indication
        elif drug_info.is_beers_list and not has_indication:
            flags.append(
                ClinicalFlag(
                    severity=Severity.MEDIUM,
                    category=FlagCategory.INDICATION,
                    finding=f"Beers List medication '{med.name}' lacks documented indication",
                    significance="High-risk medications in elderly should have clear therapeutic rationale documented.",
                    recommendation=f"Document indication for {med.name} or consider therapeutic alternatives.",
                    prescriber_action_needed=False,
                    medications_involved=[med.name],
                )
            )

    return flags


def check_lab_monitoring(
    meds: list[Medication], labs: list[LabResult]
) -> list[ClinicalFlag]:
    """Cross-reference required labs per drug."""
    flags = []
    today = date.today()

    # Build lab recency map
    lab_dates: dict[str, date] = {}
    for lab in labs:
        if lab.date:
            lab_key = lab.test_name.lower()
            if lab_key not in lab_dates or lab.date > lab_dates[lab_key]:
                lab_dates[lab_key] = lab.date

    for med in meds:
        drug_info = get_drug_info(med.name)
        if not drug_info or not drug_info.required_labs:
            continue

        for required_lab in drug_info.required_labs:
            lab_key = required_lab.lower()
            interval = LAB_MONITORING_INTERVALS.get(required_lab, 90)

            # Check if lab exists
            matching_lab = None
            for lab_name in lab_dates:
                if lab_key in lab_name or lab_name in lab_key:
                    matching_lab = lab_name
                    break

            if not matching_lab:
                flags.append(
                    ClinicalFlag(
                        severity=Severity.MEDIUM,
                        category=FlagCategory.LAB_MONITORING,
                        finding=f"Missing {required_lab} for {med.name}",
                        significance=f"{med.name} requires periodic {required_lab} monitoring for safety.",
                        recommendation=f"Order {required_lab}. Recommend monitoring every {interval} days.",
                        prescriber_action_needed=True,
                        medications_involved=[med.name],
                    )
                )
            else:
                lab_date = lab_dates[matching_lab]
                days_since = (today - lab_date).days
                if days_since > interval:
                    flags.append(
                        ClinicalFlag(
                            severity=Severity.MEDIUM,
                            category=FlagCategory.LAB_MONITORING,
                            finding=f"Overdue {required_lab} for {med.name} (last: {lab_date}, {days_since} days ago)",
                            significance=f"{required_lab} monitoring is overdue. Recommended interval is {interval} days.",
                            recommendation=f"Order {required_lab}. Previous result from {lab_date}.",
                            prescriber_action_needed=True,
                            medications_involved=[med.name],
                        )
                    )

    return flags


def check_drug_interactions(meds: list[Medication]) -> list[ClinicalFlag]:
    """Check for clinically significant drug interactions."""
    flags = []

    # Collect medications by property
    serotonergic_meds = [m.name for m in meds if _is_serotonergic(m.name)]
    qtc_meds = [m.name for m in meds if _is_qtc_prolonging(m.name)]
    cns_depressants = [m.name for m in meds if _is_cns_depressant(m.name)]
    anticholinergics = [m.name for m in meds if _is_anticholinergic(m.name)]

    # Serotonin syndrome risk
    if len(serotonergic_meds) >= 2:
        flags.append(
            ClinicalFlag(
                severity=Severity.HIGH,
                category=FlagCategory.DRUG_INTERACTION,
                finding=f"Serotonin syndrome risk: {len(serotonergic_meds)} serotonergic medications",
                significance="Concurrent serotonergic agents increase risk of serotonin syndrome "
                "(confusion, agitation, tachycardia, hyperthermia, tremor).",
                recommendation=f"Evaluate necessity of combination: {', '.join(serotonergic_meds)}. "
                "Monitor for serotonin syndrome symptoms. Consider alternatives if possible.",
                prescriber_action_needed=True,
                medications_involved=serotonergic_meds,
            )
        )

    # QTc prolongation stacking
    if len(qtc_meds) >= 2:
        severity = Severity.HIGH if len(qtc_meds) >= 3 else Severity.MEDIUM
        flags.append(
            ClinicalFlag(
                severity=severity,
                category=FlagCategory.DRUG_INTERACTION,
                finding=f"QTc prolongation risk: {len(qtc_meds)} QTc-prolonging medications",
                significance="Multiple QTc-prolonging agents increase risk of Torsades de Pointes and sudden cardiac death.",
                recommendation=f"Consider ECG monitoring. Evaluate alternatives: {', '.join(qtc_meds)}. "
                "Review electrolytes (K, Mg).",
                prescriber_action_needed=True,
                medications_involved=qtc_meds,
            )
        )

    # CNS depression stacking
    if len(cns_depressants) >= 3:
        flags.append(
            ClinicalFlag(
                severity=Severity.HIGH,
                category=FlagCategory.DRUG_INTERACTION,
                finding=f"Excessive CNS depression: {len(cns_depressants)} CNS depressants",
                significance="Multiple CNS depressants significantly increase fall risk, sedation, and respiratory depression.",
                recommendation=f"Review necessity of each: {', '.join(cns_depressants)}. "
                "Consider dose reductions or discontinuation where possible.",
                prescriber_action_needed=True,
                medications_involved=cns_depressants,
            )
        )

    # Anticholinergic burden
    total_burden = sum(_get_anticholinergic_burden(m.name) for m in meds)
    if total_burden >= 3:
        severity = Severity.HIGH if total_burden >= 6 else Severity.MEDIUM
        flags.append(
            ClinicalFlag(
                severity=severity,
                category=FlagCategory.DRUG_INTERACTION,
                finding=f"High anticholinergic burden (score: {total_burden})",
                significance="Cumulative anticholinergic burden increases risk of cognitive impairment, "
                "confusion, constipation, urinary retention, and falls.",
                recommendation=f"Review anticholinergic medications: {', '.join(anticholinergics)}. "
                "Consider alternatives with lower anticholinergic activity.",
                prescriber_action_needed=True,
                medications_involved=anticholinergics,
            )
        )

    # Duplicate therapy detection
    class_meds: dict[str, list[str]] = {}
    for med in meds:
        drug_info = get_drug_info(med.name)
        if drug_info and drug_info.drug_class:
            if drug_info.drug_class not in class_meds:
                class_meds[drug_info.drug_class] = []
            class_meds[drug_info.drug_class].append(med.name)

    for drug_class, class_med_list in class_meds.items():
        if len(class_med_list) >= 2:
            # Skip if it's expected (e.g., multiple insulins)
            if drug_class in ["insulin", "supplement"]:
                continue
            flags.append(
                ClinicalFlag(
                    severity=Severity.MEDIUM,
                    category=FlagCategory.DUPLICATE_THERAPY,
                    finding=f"Duplicate therapy: {len(class_med_list)} medications in class '{drug_class}'",
                    significance="Multiple medications from the same class may indicate therapeutic duplication.",
                    recommendation=f"Evaluate need for multiple {drug_class} agents: {', '.join(class_med_list)}.",
                    prescriber_action_needed=False,
                    medications_involved=class_med_list,
                )
            )

    return flags


def check_beers_criteria(
    meds: list[Medication], age: int | None
) -> list[ClinicalFlag]:
    """Flag all Beers list medications."""
    flags = []

    # Default to elderly if age unknown in LTC setting
    is_elderly = age is None or age >= 65

    if not is_elderly:
        return flags

    for med in meds:
        drug_info = get_drug_info(med.name)
        if not drug_info or not drug_info.is_beers_list:
            continue

        severity_map = {
            "avoid": Severity.HIGH,
            "caution": Severity.MEDIUM,
            "conditional": Severity.LOW,
        }
        severity = severity_map.get(drug_info.beers_severity or "", Severity.MEDIUM)

        flags.append(
            ClinicalFlag(
                severity=severity,
                category=FlagCategory.BEERS_CRITERIA,
                finding=f"Beers Criteria: {med.name} ({drug_info.beers_severity or 'listed'})",
                significance=drug_info.beers_rationale or "Listed on AGS Beers Criteria for potentially inappropriate medication use in older adults.",
                recommendation=f"Consider alternatives to {med.name}. If continued, document clinical rationale.",
                prescriber_action_needed=severity == Severity.HIGH,
                medications_involved=[med.name],
            )
        )

    return flags


def check_antipsychotic_compliance(meds: list[Medication]) -> list[ClinicalFlag]:
    """Check antipsychotic-specific compliance requirements."""
    flags = []

    antipsychotic_meds = [m for m in meds if _is_antipsychotic(m.name)]

    if not antipsychotic_meds:
        return flags

    # Multiple antipsychotics
    if len(antipsychotic_meds) > 1:
        names = [m.name for m in antipsychotic_meds]
        flags.append(
            ClinicalFlag(
                severity=Severity.HIGH,
                category=FlagCategory.ANTIPSYCHOTIC,
                finding=f"Multiple antipsychotics: {len(antipsychotic_meds)} concurrent agents",
                significance="CMS scrutinizes concurrent antipsychotic use. Rarely clinically justified in LTC.",
                recommendation=f"Evaluate necessity of multiple antipsychotics: {', '.join(names)}. "
                "Consider consolidation or gradual dose reduction.",
                prescriber_action_needed=True,
                medications_involved=names,
            )
        )

    # Black box warning reminder
    for med in antipsychotic_meds:
        drug_info = get_drug_info(med.name)
        if drug_info and drug_info.black_box_warnings:
            flags.append(
                ClinicalFlag(
                    severity=Severity.INFO,
                    category=FlagCategory.ANTIPSYCHOTIC,
                    finding=f"Black box warning for {med.name}",
                    significance="; ".join(drug_info.black_box_warnings),
                    recommendation="Ensure appropriate documentation and consent. Monitor for adverse effects.",
                    prescriber_action_needed=False,
                    medications_involved=[med.name],
                )
            )

    # GDR status check - note this requires start_date data
    today = date.today()
    for med in antipsychotic_meds:
        if med.start_date:
            days_on_med = (today - med.start_date).days
            if days_on_med > GDR_OVERDUE_DAYS:
                flags.append(
                    ClinicalFlag(
                        severity=Severity.HIGH,
                        category=FlagCategory.ANTIPSYCHOTIC,
                        finding=f"GDR overdue for {med.name} (started {med.start_date}, {days_on_med} days ago)",
                        significance="CMS requires Gradual Dose Reduction attempts for antipsychotics within 6 months "
                        "unless clinically contraindicated.",
                        recommendation=f"Initiate GDR for {med.name} or document clinical contraindication.",
                        prescriber_action_needed=True,
                        medications_involved=[med.name],
                    )
                )

    return flags


def check_controlled_substances(meds: list[Medication]) -> list[ClinicalFlag]:
    """Check controlled substance compliance."""
    flags = []

    # Identify controlled substances
    opioid_meds = [m for m in meds if is_opioid(m.name)]
    benzo_meds = [m for m in meds if _is_benzodiazepine(m.name)]
    controlled_meds = [m for m in meds if _is_controlled(m.name)]

    # FDA black box: opioid + benzodiazepine
    if opioid_meds and benzo_meds:
        opioid_names = [m.name for m in opioid_meds]
        benzo_names = [m.name for m in benzo_meds]
        flags.append(
            ClinicalFlag(
                severity=Severity.HIGH,
                category=FlagCategory.CONTROLLED_SUBSTANCE,
                finding="Concurrent opioid and benzodiazepine therapy (FDA Black Box Warning)",
                significance="Concurrent use of opioids and benzodiazepines increases risk of profound sedation, "
                "respiratory depression, coma, and death.",
                recommendation=f"Avoid concurrent use if possible. Opioids: {', '.join(opioid_names)}. "
                f"Benzodiazepines: {', '.join(benzo_names)}. If combination necessary, use lowest effective doses.",
                prescriber_action_needed=True,
                medications_involved=opioid_names + benzo_names,
            )
        )

    # PRN controlled substances
    prn_controlled = [m for m in controlled_meds if m.is_prn]
    if prn_controlled:
        names = [m.name for m in prn_controlled]
        flags.append(
            ClinicalFlag(
                severity=Severity.MEDIUM,
                category=FlagCategory.CONTROLLED_SUBSTANCE,
                finding=f"PRN controlled substances: {', '.join(names)}",
                significance="PRN controlled substances may indicate inadequate pain or symptom management, "
                "or potential for inappropriate use.",
                recommendation="Review PRN utilization patterns. Consider scheduled therapy if frequently used.",
                prescriber_action_needed=False,
                medications_involved=names,
            )
        )

    # Total controlled substance count
    if len(controlled_meds) >= 3:
        names = [m.name for m in controlled_meds]
        flags.append(
            ClinicalFlag(
                severity=Severity.MEDIUM,
                category=FlagCategory.CONTROLLED_SUBSTANCE,
                finding=f"Multiple controlled substances: {len(controlled_meds)} medications",
                significance="High number of controlled substances warrants review for appropriateness.",
                recommendation=f"Review necessity of each controlled substance: {', '.join(names)}.",
                prescriber_action_needed=False,
                medications_involved=names,
            )
        )

    return flags


def check_fall_risk(meds: list[Medication]) -> list[ClinicalFlag]:
    """Check for fall-risk medications."""
    flags = []

    fall_risk_meds = [m for m in meds if _is_fall_risk_med(m.name)]

    if len(fall_risk_meds) >= 3:
        names = [m.name for m in fall_risk_meds]
        severity = Severity.HIGH if len(fall_risk_meds) >= 5 else Severity.MEDIUM
        flags.append(
            ClinicalFlag(
                severity=severity,
                category=FlagCategory.FALL_RISK,
                finding=f"Elevated fall risk: {len(fall_risk_meds)} fall-risk medications",
                significance="Multiple fall-risk medications significantly increase likelihood of falls and fractures. "
                "Falls are a leading cause of morbidity and mortality in LTC.",
                recommendation=f"Review fall-risk medications: {', '.join(names)}. "
                "Consider dose reductions, alternatives, or enhanced fall precautions.",
                prescriber_action_needed=len(fall_risk_meds) >= 5,
                medications_involved=names,
            )
        )

    return flags


def check_missing_prophylaxis(meds: list[Medication]) -> list[ClinicalFlag]:
    """Check for missing prophylactic medications."""
    flags = []

    med_names = [normalize_drug_name(m.name) for m in meds]

    # Opioid without bowel regimen
    has_opioid = any(is_opioid(name) for name in med_names)
    has_bowel_med = any(is_bowel_medication(name) for name in med_names)

    if has_opioid and not has_bowel_med:
        opioid_names = [m.name for m in meds if is_opioid(m.name)]
        flags.append(
            ClinicalFlag(
                severity=Severity.MEDIUM,
                category=FlagCategory.PROPHYLAXIS,
                finding="Opioid therapy without bowel regimen",
                significance="Opioid-induced constipation is common and can lead to fecal impaction, "
                "bowel obstruction, and significant patient discomfort.",
                recommendation=f"Add bowel regimen (e.g., senna + docusate, polyethylene glycol) for "
                f"patients on {', '.join(opioid_names)}.",
                prescriber_action_needed=True,
                medications_involved=opioid_names,
            )
        )

    # Chronic steroid without calcium/vitamin D
    has_steroid = any(name in ["prednisone", "prednisolone", "dexamethasone", "methylprednisolone"]
                      for name in med_names)
    has_calcium = any("calcium" in name for name in med_names)
    has_vitamin_d = any("vitamin d" in name or "cholecalciferol" in name for name in med_names)

    if has_steroid and not (has_calcium and has_vitamin_d):
        flags.append(
            ClinicalFlag(
                severity=Severity.LOW,
                category=FlagCategory.PROPHYLAXIS,
                finding="Corticosteroid therapy without calcium/vitamin D supplementation",
                significance="Chronic corticosteroid use increases risk of osteoporosis and fractures.",
                recommendation="Consider calcium and vitamin D supplementation for bone protection.",
                prescriber_action_needed=False,
                medications_involved=[m.name for m in meds if normalize_drug_name(m.name) in
                                     ["prednisone", "prednisolone", "dexamethasone", "methylprednisolone"]],
            )
        )

    # Warfarin without recent INR (already covered in lab monitoring, but add specific note)
    has_warfarin = "warfarin" in med_names

    return flags


def calculate_complexity_score(
    flags: list[ClinicalFlag], meds: list[Medication]
) -> tuple[int, ComplexityLevel]:
    """Calculate chart complexity score."""
    score = 0

    # Points for flags by severity
    for flag in flags:
        if flag.severity == Severity.HIGH:
            score += 3
        elif flag.severity == Severity.MEDIUM:
            score += 2
        elif flag.severity == Severity.LOW:
            score += 1

    # Points for medication count
    if len(meds) >= 15:
        score += 3
    elif len(meds) >= 10:
        score += 2
    elif len(meds) >= 5:
        score += 1

    # Points for antipsychotics
    antipsychotic_count = sum(1 for m in meds if _is_antipsychotic(m.name))
    score += antipsychotic_count * 2

    # Determine level
    if score <= 5:
        level = ComplexityLevel.EASY
    elif score <= 15:
        level = ComplexityLevel.MEDIUM
    else:
        level = ComplexityLevel.HARD

    return score, level


# =============================================================================
# Helper functions
# =============================================================================


def _is_fall_risk_med(name: str) -> bool:
    """Check if medication is a fall risk."""
    drug_info = get_drug_info(name)
    return drug_info.is_fall_risk if drug_info else False


def _is_cns_depressant(name: str) -> bool:
    """Check if medication is a CNS depressant."""
    drug_info = get_drug_info(name)
    return drug_info.is_cns_depressant if drug_info else False


def _is_anticholinergic(name: str) -> bool:
    """Check if medication is anticholinergic."""
    drug_info = get_drug_info(name)
    return drug_info.is_anticholinergic if drug_info else False


def _get_anticholinergic_burden(name: str) -> int:
    """Get anticholinergic burden score for medication."""
    drug_info = get_drug_info(name)
    return drug_info.anticholinergic_burden if drug_info else 0


def _is_controlled(name: str) -> bool:
    """Check if medication is a controlled substance."""
    drug_info = get_drug_info(name)
    return drug_info.dea_schedule is not None if drug_info else False


def _is_antipsychotic(name: str) -> bool:
    """Check if medication is an antipsychotic."""
    normalized = normalize_drug_name(name)
    return normalized in ANTIPSYCHOTICS


def _is_benzodiazepine(name: str) -> bool:
    """Check if medication is a benzodiazepine."""
    normalized = normalize_drug_name(name)
    return normalized in BENZODIAZEPINES


def _is_serotonergic(name: str) -> bool:
    """Check if medication is serotonergic."""
    drug_info = get_drug_info(name)
    return drug_info.is_serotonergic if drug_info else False


def _is_qtc_prolonging(name: str) -> bool:
    """Check if medication prolongs QTc."""
    drug_info = get_drug_info(name)
    return drug_info.is_qtc_prolonging if drug_info else False


def _is_beers_list(name: str) -> bool:
    """Check if medication is on Beers list."""
    drug_info = get_drug_info(name)
    return drug_info.is_beers_list if drug_info else False


def _get_antipsychotics_needing_gdr(meds: list[Medication]) -> list[str]:
    """Get list of antipsychotics that may need GDR."""
    today = date.today()
    result = []
    for med in meds:
        if _is_antipsychotic(med.name):
            if med.start_date:
                days_on_med = (today - med.start_date).days
                if days_on_med > GDR_OVERDUE_DAYS:
                    result.append(med.name)
            else:
                # Unknown start date - flag for review
                result.append(f"{med.name} (start date unknown)")
    return result


def _get_lab_monitoring_status(
    meds: list[Medication], labs: list[LabResult]
) -> tuple[list[str], list[str]]:
    """Get lists of labs due and overdue."""
    today = date.today()
    labs_due: list[str] = []
    labs_overdue: list[str] = []

    # Build lab recency map
    lab_dates: dict[str, date] = {}
    for lab in labs:
        if lab.date:
            lab_key = lab.test_name.lower()
            if lab_key not in lab_dates or lab.date > lab_dates[lab_key]:
                lab_dates[lab_key] = lab.date

    # Check required labs for each medication
    checked_labs: set[str] = set()
    for med in meds:
        drug_info = get_drug_info(med.name)
        if not drug_info or not drug_info.required_labs:
            continue

        for required_lab in drug_info.required_labs:
            if required_lab in checked_labs:
                continue
            checked_labs.add(required_lab)

            lab_key = required_lab.lower()
            interval = LAB_MONITORING_INTERVALS.get(required_lab, 90)

            # Find matching lab
            matching_lab = None
            for lab_name in lab_dates:
                if lab_key in lab_name or lab_name in lab_key:
                    matching_lab = lab_name
                    break

            if not matching_lab:
                labs_overdue.append(required_lab)
            else:
                lab_date = lab_dates[matching_lab]
                days_since = (today - lab_date).days
                if days_since > interval:
                    labs_overdue.append(required_lab)
                elif days_since > interval - 14:  # Due within 2 weeks
                    labs_due.append(required_lab)

    return labs_due, labs_overdue
