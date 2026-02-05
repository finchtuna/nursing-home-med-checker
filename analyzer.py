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
    RecommendationRouting,
)
from drug_reference import (
    get_drug_info,
    normalize_drug_name,
    is_bowel_medication,
    is_opioid,
    is_ppi,
    is_anticoagulant,
    is_steroid_inhaler,
    is_psychotropic,
    is_antibiotic,
    is_topical_steroid,
    ANTIPSYCHOTICS,
    BENZODIAZEPINES,
    OPIOIDS,
)
from config import (
    LAB_MONITORING_INTERVALS,
    GDR_OVERDUE_DAYS,
    PPI_LONG_TERM_DAYS,
    UNUSED_PRN_DAYS,
    NEW_ADMISSION_WINDOW_DAYS,
    SUZETRIGINE_MAX_DAYS,
    TOPICAL_STEROID_REVIEW_DAYS,
    ALLERGY_CROSS_REACTIVITY,
)


def analyze_medications(parsed: ParsedChart) -> AnalysisResult:
    """Run complete clinical analysis on parsed chart data."""
    flags: list[ClinicalFlag] = []
    meds = parsed.medications
    labs = parsed.labs
    patient = parsed.patient
    diagnoses = [d.lower() for d in patient.diagnoses]
    age = patient.age

    allergies = [a.lower() for a in patient.allergies]

    # Run all original checks
    flags.extend(check_indication_verification(meds, diagnoses))
    flags.extend(check_lab_monitoring(meds, labs))
    flags.extend(check_drug_interactions(meds))
    flags.extend(check_beers_criteria(meds, age))
    flags.extend(check_antipsychotic_compliance(meds))
    flags.extend(check_controlled_substances(meds))
    flags.extend(check_fall_risk(meds))
    flags.extend(check_missing_prophylaxis(meds))

    # Run all 25 Diana-style rules
    flags.extend(check_ppi_long_term(meds))
    flags.extend(check_metformin_renal_monitoring(meds, labs))
    flags.extend(check_megace_high_risk(meds))
    flags.extend(check_fleet_enema_risk(meds, diagnoses))
    flags.extend(check_anticoagulant_monitoring(meds))
    flags.extend(check_aspirin_anticoagulant(meds))
    flags.extend(check_bupropion_seizure(meds, diagnoses))
    flags.extend(check_digoxin_diltiazem(meds))
    flags.extend(check_solifenacin_opioid(meds))
    flags.extend(check_tamsulosin_timing(meds))
    flags.extend(check_steroid_inhaler_rinse(meds))
    flags.extend(check_duplicate_prn(meds))
    flags.extend(check_unused_prn(meds))
    flags.extend(check_allergy_conflict(meds, allergies))
    flags.extend(check_hold_parameter_mismatch(meds))
    flags.extend(check_supplement_with_normal_labs(meds, labs))
    flags.extend(check_vague_pain_diagnosis(meds, diagnoses))
    flags.extend(check_topical_steroid_duration(meds))
    flags.extend(check_naloxone_without_opioid(meds))
    flags.extend(check_antibiotic_no_stop_date(meds))
    flags.extend(check_potassium_administration(meds))
    flags.extend(check_metoprolol_formulation(meds))
    flags.extend(check_suzetrigine_duration(meds))
    flags.extend(check_gdr_assessment(meds))
    flags.extend(check_new_admission_psychotropic(meds, patient))

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
# Diana-style clinical rules (25 new rules)
# =============================================================================


def check_ppi_long_term(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 1: PPI long-term use (>8 weeks)."""
    flags = []
    today = date.today()
    for med in meds:
        if is_ppi(med.name) and med.start_date:
            days_on = (today - med.start_date).days
            if days_on > PPI_LONG_TERM_DAYS:
                flags.append(ClinicalFlag(
                    severity=Severity.MEDIUM,
                    category=FlagCategory.PPI_LONG_TERM,
                    finding=f"PPI '{med.name}' in use for {days_on} days (>{PPI_LONG_TERM_DAYS} day threshold)",
                    significance="Prolonged PPI use increases risk of C. difficile infection, bone fractures, hypomagnesemia, and B12 deficiency.",
                    recommendation=f"Recommend evaluating continued need for {med.name}. Consider step-down therapy or H2 blocker alternative.",
                    prescriber_action_needed=True,
                    medications_involved=[med.name],
                    routing=RecommendationRouting.MD_PRIMARY,
                    diana_narrative=(
                        f"Resident is currently receiving {med.name} which has been in use for approximately {days_on} days. "
                        f"Per OBRA guidelines, proton pump inhibitors should be used at the lowest effective dose for the shortest "
                        f"duration necessary. Prolonged use beyond 8 weeks without clear indication (e.g., Barrett's esophagus, "
                        f"documented erosive esophagitis, Zollinger-Ellison syndrome) warrants re-evaluation. Extended PPI therapy "
                        f"is associated with increased risk of Clostridioides difficile infection, hypomagnesemia, vitamin B12 "
                        f"deficiency, and osteoporosis-related fractures. Recommend evaluating the clinical necessity of continued "
                        f"PPI therapy and considering step-down to an H2 receptor antagonist or discontinuation if appropriate."
                    ),
                    obra_reference="OBRA F-Tag 757 - Unnecessary Medications",
                    monitoring_parameters="Magnesium level, B12 level, bone density if prolonged use",
                ))
    return flags


def check_metformin_renal_monitoring(meds: list[Medication], labs: list[LabResult]) -> list[ClinicalFlag]:
    """Rule 2: Metformin renal monitoring (BMP/A1c)."""
    flags = []
    metformin_meds = [m for m in meds if normalize_drug_name(m.name) == "metformin"]
    if not metformin_meds:
        return flags

    lab_names = {lab.test_name.lower() for lab in labs}
    has_bmp = any("bmp" in l or "cmp" in l or "creatinine" in l for l in lab_names)
    has_a1c = any("a1c" in l or "hba1c" in l or "hemoglobin a1c" in l for l in lab_names)

    if not has_bmp:
        flags.append(ClinicalFlag(
            severity=Severity.HIGH,
            category=FlagCategory.RENAL_MONITORING,
            finding="Metformin without documented renal function monitoring",
            significance="Metformin is contraindicated in significant renal impairment (eGFR <30). Renal function must be monitored.",
            recommendation="Order BMP or CMP to assess renal function. Verify eGFR >30 mL/min for continued use.",
            prescriber_action_needed=True,
            medications_involved=[m.name for m in metformin_meds],
            routing=RecommendationRouting.MD_PRIMARY,
            diana_narrative=(
                "Resident is currently receiving metformin for diabetes management. No recent basic metabolic panel "
                "(BMP) or comprehensive metabolic panel (CMP) was identified in the available records. Metformin carries "
                "a black box warning for lactic acidosis and is contraindicated when eGFR falls below 30 mL/min/1.73m2. "
                "Recommend ordering a BMP to assess current renal function and ensure continued appropriateness of "
                "metformin therapy. If eGFR is between 30-45, dose adjustment should be considered."
            ),
            obra_reference="OBRA F-Tag 757 - Monitoring Requirements",
            monitoring_parameters="BMP or CMP every 3-6 months, eGFR, HbA1c every 3 months",
        ))

    if not has_a1c:
        flags.append(ClinicalFlag(
            severity=Severity.MEDIUM,
            category=FlagCategory.RENAL_MONITORING,
            finding="Metformin without documented HbA1c",
            significance="HbA1c monitoring is essential to assess glycemic control and medication effectiveness.",
            recommendation="Order HbA1c. Recommend monitoring every 3 months for patients on antidiabetic therapy.",
            prescriber_action_needed=True,
            medications_involved=[m.name for m in metformin_meds],
            routing=RecommendationRouting.MD_PRIMARY,
            diana_narrative=(
                "Resident is receiving metformin for diabetes management. No recent hemoglobin A1c (HbA1c) result "
                "was identified in the available records. HbA1c monitoring is recommended every 3 months for patients "
                "on antidiabetic therapy to assess glycemic control and guide treatment adjustments. Recommend ordering "
                "HbA1c to evaluate current glycemic status."
            ),
            monitoring_parameters="HbA1c every 3 months",
        ))
    return flags


def check_megace_high_risk(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 3: Megace (megestrol) high-risk medication."""
    flags = []
    for med in meds:
        if normalize_drug_name(med.name) == "megestrol":
            flags.append(ClinicalFlag(
                severity=Severity.HIGH,
                category=FlagCategory.HIGH_RISK_MEDICATION,
                finding=f"High-risk medication: megestrol (Megace) identified on profile",
                significance="Megestrol is on the Beers Criteria as 'avoid' - minimal efficacy for appetite/weight gain with significant thrombotic and adrenal suppression risks.",
                recommendation="Recommend evaluating continued need for megestrol. Consider non-pharmacological appetite interventions or mirtazapine as alternative.",
                prescriber_action_needed=True,
                medications_involved=[med.name],
                routing=RecommendationRouting.MD_PRIMARY,
                diana_narrative=(
                    "Resident is currently receiving megestrol acetate (Megace). Per the American Geriatrics Society "
                    "Beers Criteria, megestrol should be avoided in older adults due to minimal efficacy for appetite "
                    "stimulation and weight gain, combined with significant risk of thrombotic events, fluid retention, "
                    "and adrenal suppression. The evidence does not support meaningful clinical benefit in the geriatric "
                    "population. Recommend discussing discontinuation with the physician and considering alternative "
                    "approaches such as dietary consultation, nutrient-dense supplements, or if pharmacotherapy is desired, "
                    "mirtazapine which may promote appetite as a secondary benefit."
                ),
                obra_reference="OBRA F-Tag 757 - Beers Criteria; AGS 2023 Beers Update",
            ))
    return flags


def check_fleet_enema_risk(meds: list[Medication], diagnoses: list[str]) -> list[ClinicalFlag]:
    """Rule 4: Fleet enema + heart failure or renal impairment."""
    flags = []
    fleet_meds = [m for m in meds if "sodium phosphate" in normalize_drug_name(m.name) or "fleet" in (m.brand or "").lower()]
    if not fleet_meds:
        return flags

    risk_conditions = ["heart failure", "chf", "hf", "renal", "kidney", "ckd", "esrd"]
    has_risk = any(any(rc in d for rc in risk_conditions) for d in diagnoses)

    if has_risk:
        flags.append(ClinicalFlag(
            severity=Severity.HIGH,
            category=FlagCategory.CONTRAINDICATION,
            finding="Sodium phosphate enema (Fleet) with heart failure or renal impairment",
            significance="Fleet enemas can cause dangerous hyperphosphatemia, hypocalcemia, and electrolyte shifts in patients with renal impairment or heart failure.",
            recommendation="Discontinue Fleet enema. Substitute with a safer alternative such as tap water enema or bisacodyl suppository.",
            prescriber_action_needed=True,
            medications_involved=[m.name for m in fleet_meds],
            routing=RecommendationRouting.MD_PRIMARY,
            diana_narrative=(
                "Resident has a sodium phosphate enema (Fleet) ordered and has a documented history of heart failure "
                "and/or renal impairment. Sodium phosphate enemas are associated with significant risk of "
                "hyperphosphatemia, hypocalcemia, hypernatremia, and acute kidney injury in patients with compromised "
                "renal function or heart failure. There have been FDA safety communications and case reports of fatal "
                "electrolyte disturbances. Recommend discontinuing the sodium phosphate enema and substituting with a "
                "safer alternative such as a tap water enema or bisacodyl (Dulcolax) suppository."
            ),
            obra_reference="FDA Safety Communication - Sodium Phosphate Products",
        ))
    return flags


def check_anticoagulant_monitoring(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 5: Anticoagulant monitoring documentation."""
    flags = []
    ac_meds = [m for m in meds if is_anticoagulant(m.name)]
    if ac_meds:
        flags.append(ClinicalFlag(
            severity=Severity.LOW,
            category=FlagCategory.ANTICOAGULANT_MONITORING,
            finding=f"Anticoagulant monitoring reminder: {', '.join(m.name for m in ac_meds)}",
            significance="Anticoagulant therapy requires ongoing monitoring for signs of bleeding and appropriate lab surveillance.",
            recommendation="Ensure nursing documentation of bruising assessments, stool guaiac, and signs of bleeding per facility protocol.",
            prescriber_action_needed=False,
            medications_involved=[m.name for m in ac_meds],
            routing=RecommendationRouting.NURSING,
            diana_narrative=(
                f"Resident is receiving anticoagulant therapy ({', '.join(m.name for m in ac_meds)}). "
                f"Nursing staff should ensure ongoing documentation of bleeding assessments including skin checks "
                f"for bruising, monitoring of stool color and consistency, assessment for signs of bleeding "
                f"(epistaxis, gingival bleeding, hematuria), and prompt notification of the physician for any "
                f"concerning findings. Ensure fall prevention measures are in place given increased bleeding risk "
                f"with falls."
            ),
            monitoring_parameters="Bruising assessment, stool guaiac, signs of bleeding, fall risk precautions",
        ))
    return flags


def check_aspirin_anticoagulant(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 6: ASA + anticoagulant (OBRA HIGH SEVERITY)."""
    flags = []
    aspirin_meds = [m for m in meds if normalize_drug_name(m.name) == "aspirin"]
    ac_meds = [m for m in meds if is_anticoagulant(m.name)]

    if aspirin_meds and ac_meds:
        all_meds = [m.name for m in aspirin_meds + ac_meds]
        flags.append(ClinicalFlag(
            severity=Severity.HIGH,
            category=FlagCategory.ASPIRIN_ANTICOAGULANT,
            finding=f"Aspirin combined with anticoagulant: {', '.join(all_meds)}",
            significance="Concurrent aspirin and anticoagulant therapy significantly increases bleeding risk without clear benefit in most LTC patients.",
            recommendation="Evaluate clinical necessity of dual antithrombotic therapy. Consider discontinuing aspirin unless specific cardiac indication requires combination.",
            prescriber_action_needed=True,
            medications_involved=all_meds,
            routing=RecommendationRouting.MD_PRIMARY,
            diana_narrative=(
                f"Resident is currently receiving both aspirin and anticoagulant therapy "
                f"({', '.join(m.name for m in ac_meds)}). The combination of antiplatelet and anticoagulant "
                f"therapy significantly increases the risk of major and fatal bleeding events. Per OBRA guidelines, "
                f"this represents a HIGH SEVERITY drug-drug interaction. Unless the resident has a specific and "
                f"documented indication requiring dual antithrombotic therapy (e.g., recent coronary stent placement "
                f"within the past 12 months, mechanical heart valve), it is recommended to discontinue aspirin to "
                f"reduce bleeding risk while maintaining anticoagulation for the primary indication."
            ),
            obra_reference="OBRA F-Tag 757 - Drug-Drug Interaction, HIGH SEVERITY",
        ))
    return flags


def check_bupropion_seizure(meds: list[Medication], diagnoses: list[str]) -> list[ClinicalFlag]:
    """Rule 7: Bupropion + seizure disorder (contraindicated)."""
    flags = []
    bupropion_meds = [m for m in meds if normalize_drug_name(m.name) == "bupropion"]
    if not bupropion_meds:
        return flags

    seizure_terms = ["seizure", "epilepsy", "convulsion", "seizure disorder"]
    has_seizure = any(any(st in d for st in seizure_terms) for d in diagnoses)

    if has_seizure:
        flags.append(ClinicalFlag(
            severity=Severity.HIGH,
            category=FlagCategory.SEIZURE_CONTRAINDICATION,
            finding="Bupropion prescribed with documented seizure disorder - CONTRAINDICATED",
            significance="Bupropion lowers seizure threshold and is contraindicated in patients with seizure disorders.",
            recommendation="Discontinue bupropion. Consider alternative antidepressant that does not lower seizure threshold (e.g., sertraline, escitalopram).",
            prescriber_action_needed=True,
            medications_involved=[m.name for m in bupropion_meds],
            routing=RecommendationRouting.MD_PRIMARY,
            diana_narrative=(
                "Resident is currently receiving bupropion and has a documented history of seizure disorder. "
                "Bupropion is CONTRAINDICATED in patients with a seizure disorder due to a dose-dependent increase "
                "in seizure risk. This is listed in the product labeling as a contraindication, not merely a "
                "precaution. Recommend immediate evaluation for discontinuation of bupropion and transition to an "
                "alternative antidepressant that does not lower the seizure threshold, such as sertraline or "
                "escitalopram. If the resident requires antidepressant therapy, SSRIs are generally considered "
                "safer in patients with seizure disorders."
            ),
            obra_reference="OBRA F-Tag 757 - Contraindication",
        ))
    return flags


def check_digoxin_diltiazem(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 8: Digoxin + diltiazem interaction."""
    flags = []
    digoxin_meds = [m for m in meds if normalize_drug_name(m.name) == "digoxin"]
    diltiazem_meds = [m for m in meds if normalize_drug_name(m.name) == "diltiazem"]

    if digoxin_meds and diltiazem_meds:
        flags.append(ClinicalFlag(
            severity=Severity.HIGH,
            category=FlagCategory.DIGOXIN_INTERACTION,
            finding="Digoxin + diltiazem: significant drug interaction",
            significance="Diltiazem inhibits P-glycoprotein and increases digoxin levels by 20-40%, increasing toxicity risk.",
            recommendation="Monitor digoxin levels closely. Consider dose reduction of digoxin or alternative rate control agent.",
            prescriber_action_needed=True,
            medications_involved=["digoxin", "diltiazem"],
            routing=RecommendationRouting.MD_PRIMARY,
            diana_narrative=(
                "Resident is receiving both digoxin and diltiazem concurrently. Diltiazem inhibits P-glycoprotein "
                "and can increase serum digoxin concentrations by approximately 20-40%, significantly increasing "
                "the risk of digoxin toxicity. Signs of toxicity include nausea, vomiting, visual disturbances, "
                "and cardiac arrhythmias. Recommend obtaining a digoxin level to assess current status, and consider "
                "a dose reduction of digoxin or evaluation of an alternative rate-control strategy. Ongoing "
                "monitoring of digoxin levels and renal function is essential when these agents are co-administered."
            ),
            obra_reference="OBRA F-Tag 757 - Drug-Drug Interaction",
            monitoring_parameters="Digoxin level, heart rate, signs of toxicity (nausea, visual changes, arrhythmia)",
        ))
    return flags


def check_solifenacin_opioid(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 9: Solifenacin + opioid (urinary retention risk)."""
    flags = []
    solifenacin_meds = [m for m in meds if normalize_drug_name(m.name) == "solifenacin"]
    opioid_meds = [m for m in meds if is_opioid(m.name)]

    if solifenacin_meds and opioid_meds:
        all_names = [m.name for m in solifenacin_meds + opioid_meds]
        flags.append(ClinicalFlag(
            severity=Severity.MEDIUM,
            category=FlagCategory.URINARY_RETENTION_RISK,
            finding=f"Solifenacin combined with opioid: increased urinary retention risk",
            significance="Both anticholinergics and opioids independently increase risk of urinary retention; combination compounds this risk.",
            recommendation="Monitor for urinary retention symptoms. Consider bladder scan protocol. Evaluate necessity of solifenacin.",
            prescriber_action_needed=True,
            medications_involved=all_names,
            routing=RecommendationRouting.MD_PRIMARY,
            diana_narrative=(
                f"Resident is receiving solifenacin (Vesicare), an anticholinergic bladder medication, concurrently "
                f"with opioid therapy ({', '.join(m.name for m in opioid_meds)}). Both medication classes independently "
                f"increase the risk of urinary retention, and the combination significantly compounds this risk. "
                f"Recommend monitoring for symptoms of urinary retention (decreased urine output, bladder distension, "
                f"discomfort) and considering a bladder scan protocol. If urinary retention develops, evaluate the "
                f"continued necessity of solifenacin therapy."
            ),
            monitoring_parameters="Urinary output, bladder scan if retention suspected, post-void residual",
        ))
    return flags


def check_tamsulosin_timing(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 10: Tamsulosin AM timing -> change to bedtime."""
    flags = []
    for med in meds:
        if normalize_drug_name(med.name) == "tamsulosin":
            admin_time = (med.administration_time or "").lower()
            freq = (med.frequency or "").lower()
            if "morning" in admin_time or "am" in admin_time or "qam" in freq or "every morning" in freq:
                flags.append(ClinicalFlag(
                    severity=Severity.LOW,
                    category=FlagCategory.ADMINISTRATION_TIMING,
                    finding="Tamsulosin scheduled for morning administration - recommend bedtime dosing",
                    significance="Morning tamsulosin administration increases orthostatic hypotension and fall risk during active daytime hours.",
                    recommendation="Change tamsulosin administration time to 30 minutes after the evening meal or at bedtime.",
                    prescriber_action_needed=False,
                    medications_involved=[med.name],
                    routing=RecommendationRouting.NURSING,
                    diana_narrative=(
                        "Tamsulosin (Flomax) is currently scheduled for morning administration. Tamsulosin is an "
                        "alpha-1 adrenergic blocker that causes orthostatic hypotension, particularly within the first "
                        "few hours after dosing. Administering this medication in the morning increases the risk of "
                        "dizziness and falls during the resident's active daytime hours. Recommend changing the "
                        "administration time to 30 minutes after the evening meal or at bedtime to minimize the impact "
                        "of orthostatic effects during sleep rather than during ambulation."
                    ),
                ))
    return flags


def check_steroid_inhaler_rinse(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 11: Steroid inhaler mouth rinse recommendation."""
    flags = []
    inhaler_meds = [m for m in meds if is_steroid_inhaler(m.name)]
    if inhaler_meds:
        flags.append(ClinicalFlag(
            severity=Severity.LOW,
            category=FlagCategory.STEROID_INHALER_CARE,
            finding=f"Steroid inhaler(s) on profile: {', '.join(m.name for m in inhaler_meds)} - oral care reminder",
            significance="Inhaled corticosteroids increase risk of oral thrush (candidiasis) and hoarseness without proper oral hygiene.",
            recommendation="Ensure resident rinses mouth with water and spits after each steroid inhaler use. Document in care plan.",
            prescriber_action_needed=False,
            medications_involved=[m.name for m in inhaler_meds],
            routing=RecommendationRouting.NURSING,
            diana_narrative=(
                f"Resident is receiving inhaled corticosteroid therapy ({', '.join(m.name for m in inhaler_meds)}). "
                f"Inhaled corticosteroids deposit medication in the oropharynx and can cause oral candidiasis (thrush) "
                f"and dysphonia (hoarseness) if proper oral care is not performed after each use. Recommend ensuring "
                f"that the resident rinses mouth with water and spits (do not swallow) after each inhaler use. This "
                f"should be documented in the nursing care plan and medication administration procedures. If the "
                f"resident is unable to perform mouth rinsing independently, nursing assistance should be provided."
            ),
        ))
    return flags


def check_duplicate_prn(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 12: Duplicate PRN orders for same indication."""
    flags = []
    prn_meds = [m for m in meds if m.is_prn and m.indication]

    # Group PRN meds by indication
    indication_groups: dict[str, list[Medication]] = {}
    for med in prn_meds:
        ind_key = med.indication.lower().strip()
        if ind_key not in indication_groups:
            indication_groups[ind_key] = []
        indication_groups[ind_key].append(med)

    for indication, med_group in indication_groups.items():
        if len(med_group) >= 2:
            names = [m.name for m in med_group]
            flags.append(ClinicalFlag(
                severity=Severity.MEDIUM,
                category=FlagCategory.DUPLICATE_PRN,
                finding=f"Duplicate PRN orders for '{indication}': {', '.join(names)}",
                significance="Multiple PRN orders for the same indication creates confusion about which medication to administer and increases error risk.",
                recommendation=f"Clarify prescriber preference for PRN treatment of {indication}. Consider establishing a step-therapy order.",
                prescriber_action_needed=True,
                medications_involved=names,
                routing=RecommendationRouting.MD_PRIMARY,
                diana_narrative=(
                    f"Resident has multiple PRN (as needed) orders for the same indication of '{indication}': "
                    f"{', '.join(names)}. Having multiple PRN medications for the same indication can create confusion "
                    f"among nursing staff regarding which medication to administer, potentially leading to medication "
                    f"errors or inadvertent duplicate therapy. Recommend clarifying prescriber preference and establishing "
                    f"a clear step-therapy protocol (e.g., first-line PRN agent, then second-line if first is ineffective)."
                ),
            ))
    return flags


def check_unused_prn(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 13: Unused PRN >90 days."""
    flags = []
    today = date.today()
    for med in meds:
        if med.is_prn and med.last_used_date:
            days_unused = (today - med.last_used_date).days
            if days_unused > UNUSED_PRN_DAYS:
                flags.append(ClinicalFlag(
                    severity=Severity.LOW,
                    category=FlagCategory.UNUSED_PRN,
                    finding=f"PRN '{med.name}' unused for {days_unused} days (>{UNUSED_PRN_DAYS} day threshold)",
                    significance="PRN medications unused for extended periods add unnecessary complexity to the medication profile.",
                    recommendation=f"Consider discontinuing PRN {med.name} if no longer clinically needed.",
                    prescriber_action_needed=True,
                    medications_involved=[med.name],
                    routing=RecommendationRouting.MD_PRIMARY,
                    diana_narrative=(
                        f"PRN (as needed) order for {med.name} has not been administered for approximately {days_unused} "
                        f"days. Per OBRA guidelines, medications that have not been used for an extended period should be "
                        f"evaluated for continued necessity. Unused PRN orders add complexity to the medication profile, "
                        f"increase the risk of medication errors, and may represent an unnecessary medication. Recommend "
                        f"evaluating the continued need for this PRN order and discontinuing if no longer clinically indicated."
                    ),
                    obra_reference="OBRA F-Tag 757 - Unnecessary Medications",
                ))
    return flags


def check_allergy_conflict(meds: list[Medication], allergies: list[str]) -> list[ClinicalFlag]:
    """Rule 14: Allergy conflict verification."""
    flags = []
    if not allergies:
        return flags

    for med in meds:
        normalized = normalize_drug_name(med.name)
        for allergy in allergies:
            allergy_key = allergy.split("(")[0].strip().lower()
            # Direct match
            if allergy_key in normalized or normalized in allergy_key:
                flags.append(ClinicalFlag(
                    severity=Severity.HIGH,
                    category=FlagCategory.ALLERGY_CONFLICT,
                    finding=f"Potential allergy conflict: '{med.name}' with documented allergy to '{allergy}'",
                    significance="Medication on profile may conflict with documented allergy. Verify allergy status and medication appropriateness.",
                    recommendation=f"Verify allergy history for '{allergy}'. Confirm with prescriber that {med.name} is safe to continue.",
                    prescriber_action_needed=True,
                    medications_involved=[med.name],
                    routing=RecommendationRouting.MD_PRIMARY,
                    diana_narrative=(
                        f"Resident has a documented allergy to '{allergy}' and is currently receiving {med.name}. "
                        f"This represents a potential allergy conflict that requires verification. Recommend confirming "
                        f"the nature and severity of the documented allergy reaction, and verifying with the prescriber "
                        f"that continuation of {med.name} is clinically appropriate. If a true allergy exists, an "
                        f"alternative medication should be selected."
                    ),
                ))
                continue

            # Cross-reactivity check
            for allergy_class, cross_reactive_drugs in ALLERGY_CROSS_REACTIVITY.items():
                if allergy_key == allergy_class or any(allergy_key in cr for cr in cross_reactive_drugs):
                    if normalized in cross_reactive_drugs or any(cr in normalized for cr in cross_reactive_drugs):
                        flags.append(ClinicalFlag(
                            severity=Severity.HIGH,
                            category=FlagCategory.ALLERGY_CONFLICT,
                            finding=f"Cross-reactivity risk: '{med.name}' with allergy to '{allergy}' (class: {allergy_class})",
                            significance=f"Potential cross-reactivity between documented allergy ({allergy}) and current medication ({med.name}).",
                            recommendation=f"Evaluate cross-reactivity risk. Consider alternative medication outside the {allergy_class} class.",
                            prescriber_action_needed=True,
                            medications_involved=[med.name],
                            routing=RecommendationRouting.MD_PRIMARY,
                            diana_narrative=(
                                f"Resident has a documented allergy to '{allergy}' and is currently receiving {med.name}. "
                                f"There is potential cross-reactivity within the {allergy_class} class. While the exact "
                                f"cross-reactivity rate varies, it is recommended to verify this has been acknowledged by "
                                f"the prescriber and that the benefits outweigh the risks. If an alternative outside the "
                                f"{allergy_class} class is available, it may be preferred."
                            ),
                        ))
                        break
    return flags


def check_hold_parameter_mismatch(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 15: Differing hold parameters on BP meds."""
    flags = []
    bp_classes = {"ace inhibitor", "arb", "calcium channel blocker", "beta blocker", "alpha-1 blocker"}
    bp_meds_with_holds = [
        m for m in meds
        if m.hold_parameters and get_drug_info(m.name)
        and get_drug_info(m.name).drug_class.lower() in bp_classes
    ]

    if len(bp_meds_with_holds) >= 2:
        hold_params = set(m.hold_parameters for m in bp_meds_with_holds)
        if len(hold_params) > 1:
            names = [f"{m.name} (hold: {m.hold_parameters})" for m in bp_meds_with_holds]
            flags.append(ClinicalFlag(
                severity=Severity.LOW,
                category=FlagCategory.HOLD_PARAMETER_MISMATCH,
                finding=f"Inconsistent hold parameters on blood pressure medications: {', '.join(names)}",
                significance="Different hold parameters for BP medications can cause confusion and inconsistent blood pressure management.",
                recommendation="Recommend standardizing hold parameters across all blood pressure medications.",
                prescriber_action_needed=True,
                medications_involved=[m.name for m in bp_meds_with_holds],
                routing=RecommendationRouting.MD_PRIMARY,
                diana_narrative=(
                    f"Resident has multiple blood pressure medications with differing hold parameters: "
                    f"{'; '.join(names)}. Inconsistent hold parameters can lead to confusion among nursing staff "
                    f"regarding when to hold medications and may result in either excessive blood pressure lowering "
                    f"or inadequate blood pressure control. Recommend the physician standardize the hold parameters "
                    f"across all antihypertensive medications for clarity and consistency of care."
                ),
            ))
    return flags


def check_supplement_with_normal_labs(meds: list[Medication], labs: list[LabResult]) -> list[ClinicalFlag]:
    """Rule 16: Supplement with normal labs (e.g., NaCl + normal Na)."""
    flags = []
    supplement_lab_pairs = [
        ("sodium chloride", ["sodium", "na"], "sodium"),
        ("potassium chloride", ["potassium", "k"], "potassium"),
        ("iron", ["ferritin", "iron", "fe"], "iron"),
    ]

    for supplement_name, lab_keywords, display_name in supplement_lab_pairs:
        supp_meds = [m for m in meds if supplement_name in normalize_drug_name(m.name)]
        if not supp_meds:
            continue

        for lab in labs:
            lab_lower = lab.test_name.lower()
            if any(kw in lab_lower for kw in lab_keywords):
                if lab.flag is None or lab.flag.strip() == "":
                    flags.append(ClinicalFlag(
                        severity=Severity.LOW,
                        category=FlagCategory.SUPPLEMENT_UNNECESSARY,
                        finding=f"{display_name.title()} supplement on profile with normal {lab.test_name} level",
                        significance=f"Supplementation may not be necessary when {display_name} levels are within normal range.",
                        recommendation=f"Evaluate continued need for {display_name} supplementation given normal lab values.",
                        prescriber_action_needed=True,
                        medications_involved=[m.name for m in supp_meds],
                        routing=RecommendationRouting.MD_PRIMARY,
                        diana_narrative=(
                            f"Resident is receiving {display_name} supplementation ({', '.join(m.name for m in supp_meds)}) "
                            f"and the most recent {lab.test_name} level is within normal limits. While there may be "
                            f"clinical reasons to continue supplementation (e.g., diuretic-induced losses, dietary "
                            f"insufficiency), it is recommended to re-evaluate the continued need for this supplement "
                            f"given the normalized lab values to reduce medication burden."
                        ),
                    ))
                    break
    return flags


def check_vague_pain_diagnosis(meds: list[Medication], diagnoses: list[str]) -> list[ClinicalFlag]:
    """Rule 17: Vague pain diagnosis ('pain management')."""
    flags = []
    pain_meds = [m for m in meds if is_opioid(m.name) or normalize_drug_name(m.name) in ["gabapentin", "pregabalin"]]
    if not pain_meds:
        return flags

    vague_pain_terms = ["pain management", "chronic pain", "pain", "pain control"]
    has_vague_only = False
    specific_pain_terms = ["neuropathy", "neuropathic", "arthritis", "fracture", "radiculopathy",
                           "back pain", "osteoarthritis", "degenerative", "spinal stenosis"]

    for med in pain_meds:
        indication = (med.indication or "").lower()
        if any(v == indication.strip() for v in vague_pain_terms):
            has_specific = any(sp in indication for sp in specific_pain_terms)
            if not has_specific:
                has_vague_only = True

    if has_vague_only:
        flags.append(ClinicalFlag(
            severity=Severity.LOW,
            category=FlagCategory.VAGUE_DIAGNOSIS,
            finding="Pain medication with vague indication (e.g., 'pain management')",
            significance="Specific pain diagnosis helps guide appropriate therapy and supports OBRA documentation requirements.",
            recommendation="Recommend documenting specific pain diagnosis (e.g., osteoarthritis, neuropathy, lumbar radiculopathy).",
            prescriber_action_needed=True,
            medications_involved=[m.name for m in pain_meds],
            routing=RecommendationRouting.MD_PRIMARY,
            diana_narrative=(
                "Resident's pain medication(s) have a vague indication such as 'pain management' or 'chronic pain' "
                "without a specific diagnosis. Per OBRA guidelines, medications should have clearly documented "
                "indications that support their use. A specific pain diagnosis (e.g., osteoarthritis, diabetic "
                "neuropathy, lumbar radiculopathy, compression fracture) helps guide appropriate pharmacotherapy, "
                "supports clinical decision-making for therapy adjustments, and satisfies regulatory documentation "
                "requirements. Recommend updating the pain indication to reflect the specific underlying condition."
            ),
            obra_reference="OBRA F-Tag 757 - Indication Documentation",
        ))
    return flags


def check_topical_steroid_duration(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 18: Long-term topical steroid use."""
    flags = []
    today = date.today()
    for med in meds:
        if is_topical_steroid(med.name) and med.start_date:
            days_on = (today - med.start_date).days
            if days_on > TOPICAL_STEROID_REVIEW_DAYS:
                flags.append(ClinicalFlag(
                    severity=Severity.LOW,
                    category=FlagCategory.TOPICAL_STEROID_DURATION,
                    finding=f"Topical steroid '{med.name}' in use for {days_on} days (>{TOPICAL_STEROID_REVIEW_DAYS} day threshold)",
                    significance="Prolonged topical corticosteroid use can cause skin atrophy, striae, and systemic absorption effects.",
                    recommendation=f"Evaluate continued need for {med.name}. Consider step-down to lower potency agent or non-steroidal alternative.",
                    prescriber_action_needed=True,
                    medications_involved=[med.name],
                    routing=RecommendationRouting.MD_PRIMARY,
                    diana_narrative=(
                        f"Resident has been receiving topical corticosteroid therapy ({med.name}) for approximately "
                        f"{days_on} days. Prolonged use of topical corticosteroids, particularly mid- to high-potency "
                        f"agents, can lead to skin atrophy, telangiectasia, striae, purpura, and potential systemic "
                        f"absorption effects. Recommend evaluating the current skin condition and determining whether "
                        f"the topical steroid can be stepped down to a lower potency agent, transitioned to a "
                        f"non-steroidal alternative (e.g., tacrolimus, pimecrolimus), or discontinued."
                    ),
                ))
    return flags


def check_naloxone_without_opioid(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 19: Naloxone PRN without opioid on profile."""
    flags = []
    naloxone_meds = [m for m in meds if normalize_drug_name(m.name) == "naloxone"]
    opioid_meds = [m for m in meds if is_opioid(m.name)]

    if naloxone_meds and not opioid_meds:
        flags.append(ClinicalFlag(
            severity=Severity.LOW,
            category=FlagCategory.NALOXONE_WITHOUT_OPIOID,
            finding="Naloxone (Narcan) on profile without concurrent opioid therapy",
            significance="Naloxone without opioid on profile may indicate outdated order or unreconciled medication list.",
            recommendation="Verify whether opioid therapy has been discontinued and whether naloxone order should also be discontinued.",
            prescriber_action_needed=True,
            medications_involved=[m.name for m in naloxone_meds],
            routing=RecommendationRouting.MD_PRIMARY,
            diana_narrative=(
                "Resident has naloxone (Narcan) on the medication profile but no current opioid therapy was "
                "identified. Naloxone is indicated as a rescue medication for opioid overdose and is typically "
                "co-prescribed with opioid therapy. The absence of a concurrent opioid on the profile may indicate "
                "that opioid therapy was recently discontinued and the naloxone order was not updated accordingly, "
                "or there may be a medication reconciliation discrepancy. Recommend verifying whether naloxone "
                "is still clinically indicated or should be discontinued."
            ),
        ))
    return flags


def check_antibiotic_no_stop_date(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 20: Antibiotic with no stop date or duration."""
    flags = []
    for med in meds:
        if is_antibiotic(med.name) and not med.stop_date and not med.duration_days:
            flags.append(ClinicalFlag(
                severity=Severity.MEDIUM,
                category=FlagCategory.ANTIBIOTIC_STEWARDSHIP,
                finding=f"Antibiotic '{med.name}' without documented stop date",
                significance="Antibiotics without defined duration contribute to antibiotic resistance and increase risk of adverse effects.",
                recommendation=f"Request defined treatment duration and stop date for {med.name}. Refer to facility antibiotic stewardship program.",
                prescriber_action_needed=True,
                medications_involved=[med.name],
                routing=RecommendationRouting.ANTIBIOTIC_STEWARDSHIP,
                diana_narrative=(
                    f"Resident is receiving antibiotic therapy ({med.name}) without a documented stop date or "
                    f"defined treatment duration. Per antibiotic stewardship best practices and CMS guidelines, "
                    f"all antibiotic orders should include a specific treatment duration or stop date to prevent "
                    f"unnecessary prolonged antibiotic exposure, reduce the risk of Clostridioides difficile "
                    f"infection, minimize antibiotic resistance, and decrease adverse drug effects. Recommend "
                    f"the prescriber define a specific treatment course and stop date for this antibiotic."
                ),
                obra_reference="CMS Antibiotic Stewardship Requirements; OBRA F-Tag 881",
            ))
    return flags


def check_potassium_administration(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 21: Potassium administration instructions."""
    flags = []
    kcl_meds = [m for m in meds if "potassium" in normalize_drug_name(m.name) and "chloride" in normalize_drug_name(m.name)]
    for med in kcl_meds:
        flags.append(ClinicalFlag(
            severity=Severity.LOW,
            category=FlagCategory.POTASSIUM_ADMINISTRATION,
            finding=f"Potassium chloride on profile: verify administration with adequate fluid and food",
            significance="Potassium chloride can cause GI irritation, ulceration, and esophageal injury if not administered properly.",
            recommendation="Ensure potassium chloride is administered with a full glass of water and food. Do not crush extended-release formulation.",
            prescriber_action_needed=False,
            medications_involved=[med.name],
            routing=RecommendationRouting.NURSING,
            diana_narrative=(
                "Resident is receiving potassium chloride supplementation. Oral potassium chloride preparations "
                "can cause significant gastrointestinal irritation, esophageal ulceration, and gastric erosion if "
                "not administered properly. Nursing staff should ensure that potassium chloride is administered "
                "with a full glass of water (at least 4-8 oz) and with food to minimize GI irritation. "
                "Extended-release tablets should NOT be crushed. If the resident has difficulty swallowing tablets, "
                "consult the pharmacist regarding liquid formulation alternatives."
            ),
        ))
    return flags


def check_metoprolol_formulation(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 22: Metoprolol succinate/tartrate formulation mismatch."""
    flags = []
    metoprolol_meds = [m for m in meds if "metoprolol" in normalize_drug_name(m.name)]
    if len(metoprolol_meds) < 1:
        return flags

    for med in metoprolol_meds:
        name_lower = normalize_drug_name(med.name)
        formulation = (med.formulation or "").lower()
        freq = (med.frequency or "").lower()

        # Succinate (Toprol-XL) should be daily, tartrate (Lopressor) should be BID+
        is_succinate = "succinate" in name_lower or "succinate" in formulation or "toprol" in (med.brand or "").lower()
        is_tartrate = "tartrate" in name_lower or "tartrate" in formulation or "lopressor" in (med.brand or "").lower()

        if is_succinate and ("twice" in freq or "bid" in freq or "tid" in freq):
            flags.append(ClinicalFlag(
                severity=Severity.MEDIUM,
                category=FlagCategory.FORMULATION_MISMATCH,
                finding="Metoprolol succinate (extended-release) ordered with multiple daily dosing",
                significance="Metoprolol succinate is an extended-release formulation designed for once-daily dosing. Multiple daily dosing suggests formulation mismatch.",
                recommendation="Verify formulation: if BID dosing intended, change to metoprolol tartrate. If once-daily intended, adjust frequency.",
                prescriber_action_needed=True,
                medications_involved=[med.name],
                routing=RecommendationRouting.MD_PRIMARY,
                diana_narrative=(
                    "Metoprolol succinate (Toprol-XL) is an extended-release formulation designed for once-daily "
                    "administration, but it appears to be ordered with a multiple-times-daily frequency. This may "
                    "represent a formulation/frequency mismatch. If twice-daily or more frequent dosing is the "
                    "prescriber's intent, metoprolol tartrate (Lopressor) would be the appropriate immediate-release "
                    "formulation. Alternatively, if once-daily dosing is intended, the frequency should be corrected. "
                    "Recommend verifying the intended formulation and frequency with the prescriber."
                ),
            ))

        if is_tartrate and ("daily" in freq and "twice" not in freq and "bid" not in freq):
            flags.append(ClinicalFlag(
                severity=Severity.MEDIUM,
                category=FlagCategory.FORMULATION_MISMATCH,
                finding="Metoprolol tartrate (immediate-release) ordered once daily",
                significance="Metoprolol tartrate has a short half-life requiring twice-daily dosing. Once-daily may result in inadequate coverage.",
                recommendation="Verify formulation: if once-daily intended, change to metoprolol succinate ER. If BID intended, adjust frequency.",
                prescriber_action_needed=True,
                medications_involved=[med.name],
                routing=RecommendationRouting.MD_PRIMARY,
                diana_narrative=(
                    "Metoprolol tartrate (Lopressor) is an immediate-release formulation with a short half-life "
                    "(approximately 3-7 hours) that typically requires twice-daily or more frequent administration "
                    "for adequate therapeutic coverage. It appears to be ordered once daily, which may not provide "
                    "consistent blood pressure or heart rate control throughout the 24-hour period. If once-daily "
                    "dosing is desired, metoprolol succinate (Toprol-XL) extended-release would be more appropriate. "
                    "Recommend verifying the intended formulation and frequency with the prescriber."
                ),
            ))
    return flags


def check_suzetrigine_duration(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 23: Suzetrigine >14 day duration."""
    flags = []
    today = date.today()
    for med in meds:
        if normalize_drug_name(med.name) == "suzetrigine" and med.start_date:
            days_on = (today - med.start_date).days
            if days_on > SUZETRIGINE_MAX_DAYS:
                flags.append(ClinicalFlag(
                    severity=Severity.MEDIUM,
                    category=FlagCategory.SUZETRIGINE_DURATION,
                    finding=f"Suzetrigine (Journavx) in use for {days_on} days (>{SUZETRIGINE_MAX_DAYS} day recommended limit)",
                    significance="Suzetrigine is approved for acute pain with limited long-term safety data. Extended use beyond 14 days warrants evaluation.",
                    recommendation="Evaluate continued need for suzetrigine. Consider transitioning to an alternative analgesic for long-term pain management.",
                    prescriber_action_needed=True,
                    medications_involved=[med.name],
                    routing=RecommendationRouting.MD_PRIMARY,
                    diana_narrative=(
                        f"Resident has been receiving suzetrigine (Journavx) for approximately {days_on} days. "
                        f"Suzetrigine is a NaV1.8 sodium channel inhibitor approved for acute pain management, with "
                        f"clinical trial data primarily supporting use for up to 14 days. Long-term safety and "
                        f"efficacy data are limited at this time. Recommend evaluating the resident's current pain "
                        f"status and determining whether suzetrigine should be continued, with consideration for "
                        f"transitioning to an alternative analgesic approach if ongoing pain management is required."
                    ),
                ))
    return flags


def check_gdr_assessment(meds: list[Medication]) -> list[ClinicalFlag]:
    """Rule 24: GDR assessment template for psychotropics."""
    flags = []
    today = date.today()
    psychotropic_meds = [m for m in meds if is_psychotropic(m.name)]

    for med in psychotropic_meds:
        drug_info = get_drug_info(med.name)
        if drug_info and drug_info.requires_gdr:
            # Already handled by check_antipsychotic_compliance for antipsychotics
            # This rule adds the Diana-style narrative with GDR template for psychiatrist
            if med.start_date:
                days_on = (today - med.start_date).days
                if days_on > GDR_OVERDUE_DAYS:
                    flags.append(ClinicalFlag(
                        severity=Severity.HIGH,
                        category=FlagCategory.GDR_ASSESSMENT,
                        finding=f"Gradual Dose Reduction assessment needed for {med.name} ({days_on} days on therapy)",
                        significance="CMS requires GDR attempts for psychotropic medications unless clinically contraindicated and documented.",
                        recommendation=f"Initiate GDR assessment for {med.name}. Document clinical rationale if GDR is contraindicated.",
                        prescriber_action_needed=True,
                        medications_involved=[med.name],
                        routing=RecommendationRouting.MD_PSYCHIATRIST,
                        diana_narrative=(
                            f"Resident has been receiving {med.name} for approximately {days_on} days. Per CMS "
                            f"requirements (F-Tag 758), psychotropic medications require Gradual Dose Reduction (GDR) "
                            f"attempts unless clinically contraindicated. The GDR requirement applies within the first "
                            f"year of use and annually thereafter. A GDR attempt involves a systematic reduction in dose "
                            f"to determine if the medication can be reduced or discontinued while maintaining behavioral "
                            f"stability. If GDR is clinically contraindicated, the prescriber must document the specific "
                            f"clinical rationale supporting continued therapy at the current dose. Recommend psychiatry "
                            f"evaluate for GDR appropriateness."
                        ),
                        obra_reference="OBRA F-Tag 758 - Psychotropic Medication GDR Requirements",
                    ))
    return flags


def check_new_admission_psychotropic(meds: list[Medication], patient) -> list[ClinicalFlag]:
    """Rule 25: New admission psychotropic review."""
    flags = []
    if not patient.is_new_admission:
        # Check admission date
        if patient.admission_date:
            days_since_admission = (date.today() - patient.admission_date).days
            if days_since_admission > NEW_ADMISSION_WINDOW_DAYS:
                return flags
        else:
            return flags

    psychotropic_meds = [m for m in meds if is_psychotropic(m.name)]
    if psychotropic_meds:
        names = [m.name for m in psychotropic_meds]
        flags.append(ClinicalFlag(
            severity=Severity.MEDIUM,
            category=FlagCategory.NEW_ADMISSION_PSYCHOTROPIC,
            finding=f"New admission with psychotropic medication(s): {', '.join(names)}",
            significance="New admissions on psychotropic medications require prompt review per CMS requirements.",
            recommendation="Complete initial psychotropic medication review within 30 days of admission. Document indications and GDR plan.",
            prescriber_action_needed=True,
            medications_involved=names,
            routing=RecommendationRouting.MD_PSYCHIATRIST,
            diana_narrative=(
                f"Resident is a new admission (or within the initial 30-day review window) and is receiving "
                f"the following psychotropic medication(s): {', '.join(names)}. Per CMS requirements, all "
                f"psychotropic medications present on admission require prompt review to verify appropriate "
                f"indication, dose, and duration. The initial review should include: (1) verification of documented "
                f"psychiatric diagnosis supporting each psychotropic medication, (2) assessment of current symptom "
                f"control and behavioral status, (3) establishment of a baseline for future GDR assessment, and "
                f"(4) documentation of the treatment plan including target symptoms and monitoring parameters. "
                f"Recommend psychiatric consultation for comprehensive psychotropic medication review."
            ),
            obra_reference="OBRA F-Tag 758 - New Admission Psychotropic Review",
        ))
    return flags


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
