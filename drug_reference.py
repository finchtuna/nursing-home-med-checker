"""Curated drug reference data for LTC medication reconciliation."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DrugInfo:
    """Drug reference information."""
    generic_name: str
    brand_names: list[str] = field(default_factory=list)
    drug_class: str = ""
    therapeutic_category: str = ""
    dea_schedule: Optional[str] = None  # II, III, IV, V, or None

    # Clinical flags
    is_beers_list: bool = False
    beers_severity: Optional[str] = None  # "avoid", "caution", "conditional"
    beers_rationale: Optional[str] = None

    is_fall_risk: bool = False
    is_cns_depressant: bool = False
    is_anticholinergic: bool = False
    anticholinergic_burden: int = 0  # 1-3 scale

    is_qtc_prolonging: bool = False
    is_serotonergic: bool = False

    # Monitoring requirements
    required_labs: list[str] = field(default_factory=list)
    black_box_warnings: list[str] = field(default_factory=list)

    # For antipsychotics
    requires_gdr: bool = False

    # New flags for Diana-style rules
    is_steroid_inhaler: bool = False
    is_anticoagulant: bool = False
    is_antibiotic: bool = False
    is_psychotropic: bool = False
    is_topical_steroid: bool = False
    max_duration_days: Optional[int] = None
    seizure_contraindicated: bool = False


# =============================================================================
# ANTIPSYCHOTICS
# =============================================================================
ANTIPSYCHOTICS: dict[str, DrugInfo] = {
    "quetiapine": DrugInfo(
        generic_name="quetiapine",
        brand_names=["Seroquel", "Seroquel XR"],
        drug_class="atypical antipsychotic",
        therapeutic_category="antipsychotic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Increased risk of stroke and cognitive decline in dementia",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_anticholinergic=True,
        anticholinergic_burden=1,
        is_qtc_prolonging=True,
        is_psychotropic=True,
        required_labs=["CBC", "CMP", "HbA1c", "lipid panel"],
        black_box_warnings=[
            "Increased mortality in elderly patients with dementia-related psychosis",
            "Suicidal thoughts and behaviors in pediatric and young adult patients"
        ],
        requires_gdr=True,
    ),
    "risperidone": DrugInfo(
        generic_name="risperidone",
        brand_names=["Risperdal", "Risperdal Consta"],
        drug_class="atypical antipsychotic",
        therapeutic_category="antipsychotic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Increased risk of stroke and cognitive decline in dementia",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_qtc_prolonging=True,
        is_psychotropic=True,
        required_labs=["CBC", "CMP", "HbA1c", "lipid panel", "prolactin"],
        black_box_warnings=[
            "Increased mortality in elderly patients with dementia-related psychosis"
        ],
        requires_gdr=True,
    ),
    "olanzapine": DrugInfo(
        generic_name="olanzapine",
        brand_names=["Zyprexa", "Zyprexa Zydis"],
        drug_class="atypical antipsychotic",
        therapeutic_category="antipsychotic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Increased risk of stroke and cognitive decline in dementia; high anticholinergic",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_anticholinergic=True,
        anticholinergic_burden=2,
        is_qtc_prolonging=True,
        is_psychotropic=True,
        required_labs=["CBC", "CMP", "HbA1c", "lipid panel"],
        black_box_warnings=[
            "Increased mortality in elderly patients with dementia-related psychosis"
        ],
        requires_gdr=True,
    ),
    "aripiprazole": DrugInfo(
        generic_name="aripiprazole",
        brand_names=["Abilify", "Abilify Maintena"],
        drug_class="atypical antipsychotic",
        therapeutic_category="antipsychotic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Increased risk of stroke in dementia",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_psychotropic=True,
        required_labs=["CBC", "CMP", "HbA1c", "lipid panel"],
        black_box_warnings=[
            "Increased mortality in elderly patients with dementia-related psychosis",
            "Suicidal thoughts and behaviors"
        ],
        requires_gdr=True,
    ),
    "haloperidol": DrugInfo(
        generic_name="haloperidol",
        brand_names=["Haldol"],
        drug_class="typical antipsychotic",
        therapeutic_category="antipsychotic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Increased risk of stroke; high EPS risk",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_qtc_prolonging=True,
        is_psychotropic=True,
        required_labs=["CBC", "CMP", "ECG"],
        black_box_warnings=[
            "Increased mortality in elderly patients with dementia-related psychosis",
            "QT prolongation and Torsades de Pointes"
        ],
        requires_gdr=True,
    ),
    "brexpiprazole": DrugInfo(
        generic_name="brexpiprazole",
        brand_names=["Rexulti"],
        drug_class="atypical antipsychotic",
        therapeutic_category="antipsychotic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Increased risk of stroke in dementia",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_psychotropic=True,
        required_labs=["CBC", "CMP", "HbA1c", "lipid panel"],
        black_box_warnings=[
            "Increased mortality in elderly patients with dementia-related psychosis",
            "Suicidal thoughts and behaviors"
        ],
        requires_gdr=True,
    ),
    "pimozide": DrugInfo(
        generic_name="pimozide",
        brand_names=["Orap"],
        drug_class="typical antipsychotic",
        therapeutic_category="antipsychotic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="QTc prolongation risk; EPS",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_qtc_prolonging=True,
        is_psychotropic=True,
        required_labs=["CBC", "CMP", "ECG"],
        black_box_warnings=[
            "Increased mortality in elderly patients with dementia-related psychosis",
            "QT prolongation"
        ],
        requires_gdr=True,
    ),
    "clozapine": DrugInfo(
        generic_name="clozapine",
        brand_names=["Clozaril", "Versacloz"],
        drug_class="atypical antipsychotic",
        therapeutic_category="antipsychotic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="High anticholinergic burden; agranulocytosis risk",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_anticholinergic=True,
        anticholinergic_burden=3,
        is_qtc_prolonging=True,
        is_psychotropic=True,
        required_labs=["ANC", "CBC", "CMP", "HbA1c", "lipid panel"],
        black_box_warnings=[
            "Severe neutropenia",
            "Orthostatic hypotension and syncope",
            "Seizures",
            "Myocarditis and cardiomyopathy",
            "Increased mortality in elderly with dementia"
        ],
        requires_gdr=True,
    ),
}

# =============================================================================
# BENZODIAZEPINES
# =============================================================================
BENZODIAZEPINES: dict[str, DrugInfo] = {
    "lorazepam": DrugInfo(
        generic_name="lorazepam",
        brand_names=["Ativan"],
        drug_class="benzodiazepine",
        therapeutic_category="anxiolytic",
        dea_schedule="IV",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Older adults have increased sensitivity; risk of cognitive impairment, delirium, falls, fractures",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_psychotropic=True,
    ),
    "alprazolam": DrugInfo(
        generic_name="alprazolam",
        brand_names=["Xanax", "Xanax XR"],
        drug_class="benzodiazepine",
        therapeutic_category="anxiolytic",
        dea_schedule="IV",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Older adults have increased sensitivity; risk of cognitive impairment, delirium, falls, fractures",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_psychotropic=True,
    ),
    "temazepam": DrugInfo(
        generic_name="temazepam",
        brand_names=["Restoril"],
        drug_class="benzodiazepine",
        therapeutic_category="hypnotic",
        dea_schedule="IV",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Older adults have increased sensitivity; risk of cognitive impairment, delirium, falls, fractures",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_psychotropic=True,
    ),
    "clonazepam": DrugInfo(
        generic_name="clonazepam",
        brand_names=["Klonopin"],
        drug_class="benzodiazepine",
        therapeutic_category="anticonvulsant",
        dea_schedule="IV",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Older adults have increased sensitivity; risk of cognitive impairment, delirium, falls, fractures",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_psychotropic=True,
    ),
    "diazepam": DrugInfo(
        generic_name="diazepam",
        brand_names=["Valium"],
        drug_class="benzodiazepine",
        therapeutic_category="anxiolytic",
        dea_schedule="IV",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Long half-life; older adults more sensitive; risk of falls, cognitive impairment",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_psychotropic=True,
    ),
}

# =============================================================================
# ANTIDEPRESSANTS
# =============================================================================
ANTIDEPRESSANTS: dict[str, DrugInfo] = {
    # SSRIs
    "sertraline": DrugInfo(
        generic_name="sertraline",
        brand_names=["Zoloft"],
        drug_class="SSRI",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_qtc_prolonging=True,
        is_psychotropic=True,
    ),
    "escitalopram": DrugInfo(
        generic_name="escitalopram",
        brand_names=["Lexapro"],
        drug_class="SSRI",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_qtc_prolonging=True,
        is_psychotropic=True,
    ),
    "citalopram": DrugInfo(
        generic_name="citalopram",
        brand_names=["Celexa"],
        drug_class="SSRI",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_qtc_prolonging=True,
        is_psychotropic=True,
        is_beers_list=True,
        beers_severity="caution",
        beers_rationale="Dose-dependent QTc prolongation; avoid >20mg in elderly",
    ),
    "fluoxetine": DrugInfo(
        generic_name="fluoxetine",
        brand_names=["Prozac", "Sarafem"],
        drug_class="SSRI",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_psychotropic=True,
    ),
    "paroxetine": DrugInfo(
        generic_name="paroxetine",
        brand_names=["Paxil", "Paxil CR"],
        drug_class="SSRI",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_anticholinergic=True,
        anticholinergic_burden=2,
        is_psychotropic=True,
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Highly anticholinergic; risk of cognitive impairment",
    ),
    # SNRIs
    "venlafaxine": DrugInfo(
        generic_name="venlafaxine",
        brand_names=["Effexor", "Effexor XR"],
        drug_class="SNRI",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_psychotropic=True,
    ),
    "duloxetine": DrugInfo(
        generic_name="duloxetine",
        brand_names=["Cymbalta"],
        drug_class="SNRI",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_psychotropic=True,
    ),
    # Others
    "mirtazapine": DrugInfo(
        generic_name="mirtazapine",
        brand_names=["Remeron"],
        drug_class="tetracyclic antidepressant",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_cns_depressant=True,
        is_anticholinergic=True,
        anticholinergic_burden=1,
        is_psychotropic=True,
    ),
    "trazodone": DrugInfo(
        generic_name="trazodone",
        brand_names=["Desyrel", "Oleptro"],
        drug_class="SARI",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_cns_depressant=True,
        is_psychotropic=True,
    ),
    "bupropion": DrugInfo(
        generic_name="bupropion",
        brand_names=["Wellbutrin", "Wellbutrin SR", "Wellbutrin XL", "Zyban"],
        drug_class="NDRI",
        therapeutic_category="antidepressant",
        is_psychotropic=True,
        seizure_contraindicated=True,
        # Not serotonergic
        black_box_warnings=["Suicidal thoughts and behaviors"],
    ),
    "amitriptyline": DrugInfo(
        generic_name="amitriptyline",
        brand_names=["Elavil"],
        drug_class="tricyclic antidepressant",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_cns_depressant=True,
        is_anticholinergic=True,
        anticholinergic_burden=3,
        is_qtc_prolonging=True,
        is_psychotropic=True,
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Highly anticholinergic, sedating, orthostatic hypotension",
    ),
    "nortriptyline": DrugInfo(
        generic_name="nortriptyline",
        brand_names=["Pamelor"],
        drug_class="tricyclic antidepressant",
        therapeutic_category="antidepressant",
        is_serotonergic=True,
        is_fall_risk=True,
        is_cns_depressant=True,
        is_anticholinergic=True,
        anticholinergic_burden=2,
        is_qtc_prolonging=True,
        is_psychotropic=True,
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Anticholinergic, sedating, orthostatic hypotension",
    ),
}

# =============================================================================
# OPIOIDS
# =============================================================================
OPIOIDS: dict[str, DrugInfo] = {
    "oxycodone": DrugInfo(
        generic_name="oxycodone",
        brand_names=["OxyContin", "Roxicodone", "Percocet"],
        drug_class="opioid",
        therapeutic_category="analgesic",
        dea_schedule="II",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Risk of respiratory depression, falls, constipation, delirium",
        is_fall_risk=True,
        is_cns_depressant=True,
        black_box_warnings=[
            "Risk of addiction, abuse, and misuse",
            "Life-threatening respiratory depression",
            "Neonatal opioid withdrawal syndrome",
            "Risks with concurrent benzodiazepine use"
        ],
    ),
    "hydrocodone": DrugInfo(
        generic_name="hydrocodone",
        brand_names=["Vicodin", "Norco", "Lortab"],
        drug_class="opioid",
        therapeutic_category="analgesic",
        dea_schedule="II",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Risk of respiratory depression, falls, constipation, delirium",
        is_fall_risk=True,
        is_cns_depressant=True,
        black_box_warnings=[
            "Risk of addiction, abuse, and misuse",
            "Life-threatening respiratory depression",
            "Risks with concurrent benzodiazepine use"
        ],
    ),
    "morphine": DrugInfo(
        generic_name="morphine",
        brand_names=["MS Contin", "Kadian", "Roxanol"],
        drug_class="opioid",
        therapeutic_category="analgesic",
        dea_schedule="II",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Risk of respiratory depression, falls, constipation, delirium",
        is_fall_risk=True,
        is_cns_depressant=True,
        black_box_warnings=[
            "Risk of addiction, abuse, and misuse",
            "Life-threatening respiratory depression",
            "Risks with concurrent benzodiazepine use"
        ],
    ),
    "fentanyl": DrugInfo(
        generic_name="fentanyl",
        brand_names=["Duragesic", "Actiq", "Subsys"],
        drug_class="opioid",
        therapeutic_category="analgesic",
        dea_schedule="II",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Risk of respiratory depression, falls, accidental exposure",
        is_fall_risk=True,
        is_cns_depressant=True,
        black_box_warnings=[
            "Risk of addiction, abuse, and misuse",
            "Life-threatening respiratory depression",
            "Accidental exposure can be fatal",
            "Risks with concurrent benzodiazepine use",
            "REMS required for transmucosal products"
        ],
    ),
    "tramadol": DrugInfo(
        generic_name="tramadol",
        brand_names=["Ultram", "ConZip"],
        drug_class="opioid",
        therapeutic_category="analgesic",
        dea_schedule="IV",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="CNS effects, serotonin syndrome risk, seizure risk",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_serotonergic=True,
        black_box_warnings=[
            "Risk of addiction, abuse, and misuse",
            "Life-threatening respiratory depression",
            "Risks with concurrent benzodiazepine use",
            "Serotonin syndrome risk"
        ],
    ),
    "codeine": DrugInfo(
        generic_name="codeine",
        brand_names=["Tylenol #3", "Tylenol #4"],
        drug_class="opioid",
        therapeutic_category="analgesic",
        dea_schedule="II",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Constipation, falls risk, unpredictable metabolism",
        is_fall_risk=True,
        is_cns_depressant=True,
    ),
}

# =============================================================================
# CHRONIC DISEASE MEDICATIONS
# =============================================================================
CHRONIC_DISEASE_MEDS: dict[str, DrugInfo] = {
    # Anticoagulants
    "warfarin": DrugInfo(
        generic_name="warfarin",
        brand_names=["Coumadin", "Jantoven"],
        drug_class="anticoagulant",
        therapeutic_category="anticoagulant",
        is_fall_risk=True,
        is_anticoagulant=True,
        required_labs=["INR", "CBC"],
        black_box_warnings=["Bleeding risk"],
    ),
    "apixaban": DrugInfo(
        generic_name="apixaban",
        brand_names=["Eliquis"],
        drug_class="DOAC",
        therapeutic_category="anticoagulant",
        is_fall_risk=True,
        is_anticoagulant=True,
        required_labs=["CBC", "CrCl"],
        black_box_warnings=["Bleeding risk", "Spinal hematoma risk with neuraxial anesthesia"],
    ),
    "rivaroxaban": DrugInfo(
        generic_name="rivaroxaban",
        brand_names=["Xarelto"],
        drug_class="DOAC",
        therapeutic_category="anticoagulant",
        is_fall_risk=True,
        is_anticoagulant=True,
        required_labs=["CBC", "CrCl"],
        black_box_warnings=["Bleeding risk", "Spinal hematoma risk"],
    ),
    # Diabetes
    "metformin": DrugInfo(
        generic_name="metformin",
        brand_names=["Glucophage", "Glumetza"],
        drug_class="biguanide",
        therapeutic_category="antidiabetic",
        required_labs=["CMP", "HbA1c", "B12"],
        black_box_warnings=["Lactic acidosis"],
    ),
    "insulin glargine": DrugInfo(
        generic_name="insulin glargine",
        brand_names=["Lantus", "Basaglar", "Toujeo"],
        drug_class="insulin",
        therapeutic_category="antidiabetic",
        is_fall_risk=True,
        required_labs=["HbA1c", "BMP"],
    ),
    "insulin lispro": DrugInfo(
        generic_name="insulin lispro",
        brand_names=["Humalog"],
        drug_class="insulin",
        therapeutic_category="antidiabetic",
        is_fall_risk=True,
        required_labs=["HbA1c", "BMP"],
    ),
    "glipizide": DrugInfo(
        generic_name="glipizide",
        brand_names=["Glucotrol"],
        drug_class="sulfonylurea",
        therapeutic_category="antidiabetic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Higher risk of hypoglycemia; long duration of action",
        is_fall_risk=True,
        required_labs=["HbA1c", "BMP"],
    ),
    "glyburide": DrugInfo(
        generic_name="glyburide",
        brand_names=["DiaBeta", "Glynase"],
        drug_class="sulfonylurea",
        therapeutic_category="antidiabetic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Higher risk of severe prolonged hypoglycemia in older adults",
        is_fall_risk=True,
        required_labs=["HbA1c", "BMP"],
    ),
    # Thyroid
    "levothyroxine": DrugInfo(
        generic_name="levothyroxine",
        brand_names=["Synthroid", "Levoxyl", "Tirosint"],
        drug_class="thyroid hormone",
        therapeutic_category="thyroid",
        required_labs=["TSH", "free T4"],
    ),
    # Cardiovascular - ACE/ARBs
    "lisinopril": DrugInfo(
        generic_name="lisinopril",
        brand_names=["Prinivil", "Zestril"],
        drug_class="ACE inhibitor",
        therapeutic_category="antihypertensive",
        is_fall_risk=True,
        required_labs=["CMP", "potassium"],
    ),
    "losartan": DrugInfo(
        generic_name="losartan",
        brand_names=["Cozaar"],
        drug_class="ARB",
        therapeutic_category="antihypertensive",
        is_fall_risk=True,
        required_labs=["CMP", "potassium"],
    ),
    "amlodipine": DrugInfo(
        generic_name="amlodipine",
        brand_names=["Norvasc"],
        drug_class="calcium channel blocker",
        therapeutic_category="antihypertensive",
        is_fall_risk=True,
    ),
    # Statins
    "atorvastatin": DrugInfo(
        generic_name="atorvastatin",
        brand_names=["Lipitor"],
        drug_class="statin",
        therapeutic_category="antihyperlipidemic",
        required_labs=["lipid panel", "LFTs"],
    ),
    "simvastatin": DrugInfo(
        generic_name="simvastatin",
        brand_names=["Zocor"],
        drug_class="statin",
        therapeutic_category="antihyperlipidemic",
        required_labs=["lipid panel", "LFTs"],
    ),
    "rosuvastatin": DrugInfo(
        generic_name="rosuvastatin",
        brand_names=["Crestor"],
        drug_class="statin",
        therapeutic_category="antihyperlipidemic",
        required_labs=["lipid panel", "LFTs"],
    ),
    # Mood stabilizers
    "lithium": DrugInfo(
        generic_name="lithium",
        brand_names=["Lithobid", "Eskalith"],
        drug_class="mood stabilizer",
        therapeutic_category="psychiatric",
        is_fall_risk=True,
        required_labs=["lithium level", "TSH", "CMP", "BUN", "creatinine"],
        black_box_warnings=["Lithium toxicity"],
    ),
    "valproic acid": DrugInfo(
        generic_name="valproic acid",
        brand_names=["Depakote", "Depakene"],
        drug_class="anticonvulsant/mood stabilizer",
        therapeutic_category="psychiatric",
        is_fall_risk=True,
        is_cns_depressant=True,
        required_labs=["valproic acid level", "CBC", "LFTs", "ammonia"],
        black_box_warnings=["Hepatotoxicity", "Pancreatitis", "Teratogenicity"],
    ),
    "carbamazepine": DrugInfo(
        generic_name="carbamazepine",
        brand_names=["Tegretol"],
        drug_class="anticonvulsant",
        therapeutic_category="anticonvulsant",
        is_fall_risk=True,
        is_cns_depressant=True,
        required_labs=["carbamazepine level", "CBC", "CMP", "LFTs"],
        black_box_warnings=["Aplastic anemia", "Agranulocytosis", "SJS/TEN"],
    ),
    # GI
    "omeprazole": DrugInfo(
        generic_name="omeprazole",
        brand_names=["Prilosec"],
        drug_class="PPI",
        therapeutic_category="GI",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Risk of C. diff, bone loss, B12 deficiency with prolonged use (>8 weeks)",
    ),
    "pantoprazole": DrugInfo(
        generic_name="pantoprazole",
        brand_names=["Protonix"],
        drug_class="PPI",
        therapeutic_category="GI",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Risk of C. diff, bone loss, B12 deficiency with prolonged use (>8 weeks)",
    ),
    "lansoprazole": DrugInfo(
        generic_name="lansoprazole",
        brand_names=["Prevacid"],
        drug_class="PPI",
        therapeutic_category="GI",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Risk of C. diff, bone loss, B12 deficiency with prolonged use (>8 weeks)",
    ),
    # Bowel regimen
    "docusate": DrugInfo(
        generic_name="docusate",
        brand_names=["Colace"],
        drug_class="stool softener",
        therapeutic_category="GI",
    ),
    "senna": DrugInfo(
        generic_name="senna",
        brand_names=["Senokot"],
        drug_class="stimulant laxative",
        therapeutic_category="GI",
    ),
    "polyethylene glycol": DrugInfo(
        generic_name="polyethylene glycol",
        brand_names=["MiraLAX"],
        drug_class="osmotic laxative",
        therapeutic_category="GI",
    ),
    "bisacodyl": DrugInfo(
        generic_name="bisacodyl",
        brand_names=["Dulcolax"],
        drug_class="stimulant laxative",
        therapeutic_category="GI",
    ),
    # Steroids
    "prednisone": DrugInfo(
        generic_name="prednisone",
        brand_names=["Deltasone"],
        drug_class="corticosteroid",
        therapeutic_category="anti-inflammatory",
        required_labs=["BMP", "glucose"],
    ),
    # Supplements
    "calcium carbonate": DrugInfo(
        generic_name="calcium carbonate",
        brand_names=["Tums", "Os-Cal"],
        drug_class="supplement",
        therapeutic_category="supplement",
    ),
    "vitamin d": DrugInfo(
        generic_name="vitamin d",
        brand_names=["Drisdol", "Calciferol"],
        drug_class="supplement",
        therapeutic_category="supplement",
    ),
    "cholecalciferol": DrugInfo(
        generic_name="cholecalciferol",
        brand_names=["Vitamin D3"],
        drug_class="supplement",
        therapeutic_category="supplement",
    ),
}

# =============================================================================
# OTHER COMMONLY USED MEDICATIONS
# =============================================================================
OTHER_MEDS: dict[str, DrugInfo] = {
    # Muscle relaxants
    "cyclobenzaprine": DrugInfo(
        generic_name="cyclobenzaprine",
        brand_names=["Flexeril"],
        drug_class="muscle relaxant",
        therapeutic_category="musculoskeletal",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Highly anticholinergic; effectiveness questionable in elderly",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_anticholinergic=True,
        anticholinergic_burden=3,
    ),
    "methocarbamol": DrugInfo(
        generic_name="methocarbamol",
        brand_names=["Robaxin"],
        drug_class="muscle relaxant",
        therapeutic_category="musculoskeletal",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Poorly tolerated in elderly; anticholinergic effects",
        is_fall_risk=True,
        is_cns_depressant=True,
    ),
    "carisoprodol": DrugInfo(
        generic_name="carisoprodol",
        brand_names=["Soma"],
        drug_class="muscle relaxant",
        therapeutic_category="musculoskeletal",
        dea_schedule="IV",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Poorly tolerated; sedation; abuse potential",
        is_fall_risk=True,
        is_cns_depressant=True,
    ),
    # Antihistamines
    "diphenhydramine": DrugInfo(
        generic_name="diphenhydramine",
        brand_names=["Benadryl"],
        drug_class="antihistamine",
        therapeutic_category="allergy/sleep",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Highly anticholinergic; confusion, dry mouth, constipation, urinary retention",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_anticholinergic=True,
        anticholinergic_burden=3,
    ),
    "hydroxyzine": DrugInfo(
        generic_name="hydroxyzine",
        brand_names=["Vistaril", "Atarax"],
        drug_class="antihistamine",
        therapeutic_category="anxiolytic",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Highly anticholinergic",
        is_fall_risk=True,
        is_cns_depressant=True,
        is_anticholinergic=True,
        anticholinergic_burden=2,
    ),
    # Sleep medications
    "zolpidem": DrugInfo(
        generic_name="zolpidem",
        brand_names=["Ambien", "Ambien CR"],
        drug_class="non-benzodiazepine hypnotic",
        therapeutic_category="hypnotic",
        dea_schedule="IV",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Similar to benzos: delirium, falls, fractures; minimal improvement in sleep",
        is_fall_risk=True,
        is_cns_depressant=True,
    ),
    "eszopiclone": DrugInfo(
        generic_name="eszopiclone",
        brand_names=["Lunesta"],
        drug_class="non-benzodiazepine hypnotic",
        therapeutic_category="hypnotic",
        dea_schedule="IV",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Similar to benzos: delirium, falls, fractures",
        is_fall_risk=True,
        is_cns_depressant=True,
    ),
    # Digoxin
    "digoxin": DrugInfo(
        generic_name="digoxin",
        brand_names=["Lanoxin"],
        drug_class="cardiac glycoside",
        therapeutic_category="cardiac",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Increased risk of toxicity due to decreased renal clearance",
        required_labs=["digoxin level", "CMP", "potassium", "magnesium"],
    ),
    # Gabapentinoids
    "gabapentin": DrugInfo(
        generic_name="gabapentin",
        brand_names=["Neurontin", "Gralise"],
        drug_class="gabapentinoid",
        therapeutic_category="anticonvulsant/analgesic",
        is_fall_risk=True,
        is_cns_depressant=True,
        required_labs=["CrCl"],
    ),
    "pregabalin": DrugInfo(
        generic_name="pregabalin",
        brand_names=["Lyrica"],
        drug_class="gabapentinoid",
        therapeutic_category="anticonvulsant/analgesic",
        dea_schedule="V",
        is_fall_risk=True,
        is_cns_depressant=True,
        required_labs=["CrCl"],
    ),
    # Anticholinergics for bladder
    "oxybutynin": DrugInfo(
        generic_name="oxybutynin",
        brand_names=["Ditropan"],
        drug_class="anticholinergic",
        therapeutic_category="urological",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Highly anticholinergic; cognitive impairment; delirium risk",
        is_anticholinergic=True,
        anticholinergic_burden=3,
        is_fall_risk=True,
    ),
    "tolterodine": DrugInfo(
        generic_name="tolterodine",
        brand_names=["Detrol", "Detrol LA"],
        drug_class="anticholinergic",
        therapeutic_category="urological",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Anticholinergic; cognitive impairment",
        is_anticholinergic=True,
        anticholinergic_burden=2,
        is_fall_risk=True,
    ),
}

# =============================================================================
# NEW DRUGS FOR DIANA-STYLE RULES
# =============================================================================
DIANA_RULE_MEDS: dict[str, DrugInfo] = {
    "megestrol": DrugInfo(
        generic_name="megestrol",
        brand_names=["Megace", "Megace ES"],
        drug_class="progestin",
        therapeutic_category="appetite stimulant",
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Minimal efficacy for weight gain in elderly; thrombotic risk, fluid retention",
    ),
    "sodium phosphate enema": DrugInfo(
        generic_name="sodium phosphate enema",
        brand_names=["Fleet Enema", "Fleet"],
        drug_class="saline laxative",
        therapeutic_category="GI",
    ),
    "solifenacin": DrugInfo(
        generic_name="solifenacin",
        brand_names=["Vesicare"],
        drug_class="anticholinergic",
        therapeutic_category="urological",
        is_anticholinergic=True,
        anticholinergic_burden=2,
        is_beers_list=True,
        beers_severity="avoid",
        beers_rationale="Anticholinergic; cognitive impairment risk",
    ),
    "tamsulosin": DrugInfo(
        generic_name="tamsulosin",
        brand_names=["Flomax"],
        drug_class="alpha-1 blocker",
        therapeutic_category="urological",
        is_fall_risk=True,
    ),
    "diltiazem": DrugInfo(
        generic_name="diltiazem",
        brand_names=["Cardizem", "Cardizem CD", "Tiazac", "Dilacor"],
        drug_class="calcium channel blocker",
        therapeutic_category="antihypertensive",
        is_fall_risk=True,
    ),
    "aspirin": DrugInfo(
        generic_name="aspirin",
        brand_names=["Bayer", "Ecotrin"],
        drug_class="antiplatelet",
        therapeutic_category="antiplatelet",
    ),
    "naloxone": DrugInfo(
        generic_name="naloxone",
        brand_names=["Narcan"],
        drug_class="opioid antagonist",
        therapeutic_category="antidote",
    ),
    "suzetrigine": DrugInfo(
        generic_name="suzetrigine",
        brand_names=["Journavx"],
        drug_class="NaV1.8 inhibitor",
        therapeutic_category="analgesic",
        max_duration_days=14,
    ),
    "metoprolol succinate": DrugInfo(
        generic_name="metoprolol succinate",
        brand_names=["Toprol-XL"],
        drug_class="beta blocker",
        therapeutic_category="antihypertensive",
        is_fall_risk=True,
    ),
    "metoprolol tartrate": DrugInfo(
        generic_name="metoprolol tartrate",
        brand_names=["Lopressor"],
        drug_class="beta blocker",
        therapeutic_category="antihypertensive",
        is_fall_risk=True,
    ),
    "potassium chloride": DrugInfo(
        generic_name="potassium chloride",
        brand_names=["K-Dur", "Klor-Con", "Micro-K"],
        drug_class="electrolyte supplement",
        therapeutic_category="supplement",
        required_labs=["potassium", "BMP"],
    ),
    "fluticasone-salmeterol": DrugInfo(
        generic_name="fluticasone-salmeterol",
        brand_names=["Advair", "Advair Diskus", "Advair HFA", "AirDuo"],
        drug_class="steroid inhaler + LABA",
        therapeutic_category="respiratory",
        is_steroid_inhaler=True,
    ),
    "budesonide-formoterol": DrugInfo(
        generic_name="budesonide-formoterol",
        brand_names=["Symbicort"],
        drug_class="steroid inhaler + LABA",
        therapeutic_category="respiratory",
        is_steroid_inhaler=True,
    ),
    "fluticasone": DrugInfo(
        generic_name="fluticasone",
        brand_names=["Flovent", "Flovent HFA", "ArmonAir"],
        drug_class="inhaled corticosteroid",
        therapeutic_category="respiratory",
        is_steroid_inhaler=True,
    ),
    "budesonide inhaler": DrugInfo(
        generic_name="budesonide inhaler",
        brand_names=["Pulmicort"],
        drug_class="inhaled corticosteroid",
        therapeutic_category="respiratory",
        is_steroid_inhaler=True,
    ),
    "mometasone-formoterol": DrugInfo(
        generic_name="mometasone-formoterol",
        brand_names=["Dulera"],
        drug_class="steroid inhaler + LABA",
        therapeutic_category="respiratory",
        is_steroid_inhaler=True,
    ),
    "sodium chloride": DrugInfo(
        generic_name="sodium chloride",
        brand_names=["NaCl tabs"],
        drug_class="electrolyte supplement",
        therapeutic_category="supplement",
        required_labs=["sodium", "BMP"],
    ),
    "triamcinolone topical": DrugInfo(
        generic_name="triamcinolone topical",
        brand_names=["Kenalog topical"],
        drug_class="topical corticosteroid",
        therapeutic_category="dermatological",
        is_topical_steroid=True,
    ),
    "betamethasone topical": DrugInfo(
        generic_name="betamethasone topical",
        brand_names=["Diprolene"],
        drug_class="topical corticosteroid",
        therapeutic_category="dermatological",
        is_topical_steroid=True,
    ),
    "clobetasol topical": DrugInfo(
        generic_name="clobetasol topical",
        brand_names=["Temovate", "Clobex"],
        drug_class="topical corticosteroid",
        therapeutic_category="dermatological",
        is_topical_steroid=True,
    ),
    # PCC-observed medications
    "levetiracetam": DrugInfo(
        generic_name="levetiracetam",
        brand_names=["Keppra"],
        drug_class="anticonvulsant",
        therapeutic_category="anticonvulsant",
        is_fall_risk=True,
        is_cns_depressant=True,
        required_labs=["drug level"],
    ),
    "meropenem": DrugInfo(
        generic_name="meropenem",
        brand_names=["Merrem"],
        drug_class="carbapenem antibiotic",
        therapeutic_category="antibiotic",
        is_antibiotic=True,
        required_labs=["CBC", "CMP"],
    ),
    "glycopyrrolate": DrugInfo(
        generic_name="glycopyrrolate",
        brand_names=["Robinul", "Cuvposa"],
        drug_class="anticholinergic",
        therapeutic_category="respiratory",
        is_anticholinergic=True,
        anticholinergic_burden=2,
    ),
    "ondansetron": DrugInfo(
        generic_name="ondansetron",
        brand_names=["Zofran"],
        drug_class="5-HT3 antagonist",
        therapeutic_category="antiemetic",
        is_qtc_prolonging=True,
    ),
    "acetaminophen": DrugInfo(
        generic_name="acetaminophen",
        brand_names=["Tylenol"],
        drug_class="analgesic",
        therapeutic_category="analgesic",
    ),
    "albuterol": DrugInfo(
        generic_name="albuterol",
        brand_names=["ProAir", "Ventolin", "Proventil"],
        drug_class="short-acting beta-agonist",
        therapeutic_category="respiratory",
    ),
    "ipratropium-albuterol": DrugInfo(
        generic_name="ipratropium-albuterol",
        brand_names=["DuoNeb", "Combivent"],
        drug_class="anticholinergic + SABA combo",
        therapeutic_category="respiratory",
        is_anticholinergic=True,
        anticholinergic_burden=1,
    ),
    "ferrous sulfate": DrugInfo(
        generic_name="ferrous sulfate",
        brand_names=["Feosol", "Fer-In-Sol"],
        drug_class="iron supplement",
        therapeutic_category="supplement",
    ),
    "magnesium hydroxide": DrugInfo(
        generic_name="magnesium hydroxide",
        brand_names=["Milk of Magnesia", "Phillips"],
        drug_class="antacid/laxative",
        therapeutic_category="GI",
    ),
    "nystatin": DrugInfo(
        generic_name="nystatin",
        brand_names=["Mycostatin", "Nystop"],
        drug_class="antifungal",
        therapeutic_category="antifungal",
    ),
    "miconazole": DrugInfo(
        generic_name="miconazole",
        brand_names=["Monistat", "Micatin"],
        drug_class="antifungal",
        therapeutic_category="antifungal/topical",
    ),
    "enoxaparin": DrugInfo(
        generic_name="enoxaparin",
        brand_names=["Lovenox"],
        drug_class="LMWH anticoagulant",
        therapeutic_category="anticoagulant",
        is_anticoagulant=True,
        is_fall_risk=True,
        required_labs=["CBC", "platelet count"],
    ),
    "zinc oxide": DrugInfo(
        generic_name="zinc oxide",
        brand_names=["Desitin", "Boudreaux's"],
        drug_class="skin protectant",
        therapeutic_category="dermatological",
    ),
    "phenytoin": DrugInfo(
        generic_name="phenytoin",
        brand_names=["Dilantin", "Phenytek"],
        drug_class="anticonvulsant",
        therapeutic_category="anticonvulsant",
        is_fall_risk=True,
        is_cns_depressant=True,
        required_labs=["phenytoin level", "CBC", "CMP", "albumin"],
    ),
    "guaifenesin": DrugInfo(
        generic_name="guaifenesin",
        brand_names=["Mucinex", "Robitussin"],
        drug_class="expectorant",
        therapeutic_category="respiratory",
    ),
}

# =============================================================================
# COMBINED DRUG DATABASE
# =============================================================================
ALL_DRUGS: dict[str, DrugInfo] = {
    **ANTIPSYCHOTICS,
    **BENZODIAZEPINES,
    **ANTIDEPRESSANTS,
    **OPIOIDS,
    **CHRONIC_DISEASE_MEDS,
    **OTHER_MEDS,
    **DIANA_RULE_MEDS,
}

# Brand to generic mapping
BRAND_TO_GENERIC: dict[str, str] = {}
for drug_name, drug_info in ALL_DRUGS.items():
    for brand in drug_info.brand_names:
        BRAND_TO_GENERIC[brand.lower()] = drug_name

# Common frequency normalizations
FREQUENCY_MAP: dict[str, str] = {
    "qd": "daily",
    "od": "daily",
    "qam": "every morning",
    "qpm": "every evening",
    "qhs": "at bedtime",
    "hs": "at bedtime",
    "bid": "twice daily",
    "tid": "three times daily",
    "qid": "four times daily",
    "q4h": "every 4 hours",
    "q6h": "every 6 hours",
    "q8h": "every 8 hours",
    "q12h": "every 12 hours",
    "prn": "as needed",
    "ac": "before meals",
    "pc": "after meals",
    "c": "with",
    "stat": "immediately",
    "weekly": "once weekly",
    "qweek": "once weekly",
    "biweekly": "every 2 weeks",
    "monthly": "once monthly",
    # PCC natural-language frequencies
    "2 times a day": "twice daily",
    "3 times a day": "three times daily",
    "4 times a day": "four times daily",
    "every 8 hours": "every 8 hours",
    "every 6 hours": "every 6 hours",
    "every 4 hours": "every 4 hours",
    "every 12 hours": "every 12 hours",
    "once a day": "daily",
    "once daily": "daily",
    "every other day": "every other day",
    "every night at bedtime": "at bedtime",
    "every morning": "every morning",
    "every evening": "every evening",
}


def _strip_salt_suffix(name: str) -> str:
    """Strip common pharmaceutical salt suffixes from drug names.

    Only strips the suffix if the base name (without suffix) is a known drug.
    This prevents stripping from drug names where the 'salt' word is integral
    (e.g., 'ferrous sulfate' stays as-is).
    """
    salt_suffixes = [
        "calcium", "sodium", "hydrochloride", "hcl", "mesylate",
        "besylate", "maleate", "fumarate", "potassium", "sulfate",
        "acetate", "phosphate", "citrate", "tartrate", "succinate",
        "bromide", "chloride", "nitrate", "oxalate",
    ]
    for suffix in salt_suffixes:
        if name.endswith(" " + suffix):
            base = name[: -(len(suffix) + 1)].strip()
            if base in ALL_DRUGS or base in BRAND_TO_GENERIC:
                return base
    return name


def normalize_drug_name(name: str) -> str:
    """Normalize a drug name to its generic form."""
    if not name:
        return ""

    name_lower = name.lower().strip()

    # Check if it's already a generic name
    if name_lower in ALL_DRUGS:
        return name_lower

    # Check brand name mapping
    if name_lower in BRAND_TO_GENERIC:
        return BRAND_TO_GENERIC[name_lower]

    # Try stripping salt suffix
    stripped = _strip_salt_suffix(name_lower)
    if stripped != name_lower:
        if stripped in ALL_DRUGS:
            return stripped
        if stripped in BRAND_TO_GENERIC:
            return BRAND_TO_GENERIC[stripped]

    # Check if name is a prefix of a known drug (e.g., "metoprolol" -> "metoprolol tartrate")
    prefix_matches = [drug for drug in ALL_DRUGS if drug.startswith(name_lower + " ")]
    if len(prefix_matches) >= 1:
        return prefix_matches[0]

    # Check partial matches (e.g., "Seroquel XR" -> "quetiapine")
    for brand, generic in BRAND_TO_GENERIC.items():
        if brand in name_lower or name_lower in brand:
            return generic

    # Return original name if not found (may be unlisted drug)
    return name_lower


def get_drug_info(name: str) -> DrugInfo | None:
    """Get drug information by generic or brand name."""
    normalized = normalize_drug_name(name)
    return ALL_DRUGS.get(normalized)


def get_drug_class(name: str) -> str | None:
    """Get the drug class for a medication."""
    info = get_drug_info(name)
    return info.drug_class if info else None


def get_brand_to_generic_map() -> dict[str, str]:
    """Get the complete brand-to-generic mapping."""
    return BRAND_TO_GENERIC.copy()


def is_bowel_medication(name: str) -> bool:
    """Check if a medication is part of a bowel regimen."""
    normalized = normalize_drug_name(name)
    bowel_meds = {"docusate", "senna", "polyethylene glycol", "bisacodyl", "lactulose",
                  "miralax", "magnesium hydroxide", "milk of magnesia"}
    return normalized in bowel_meds or any(b in normalized for b in bowel_meds)


def is_opioid(name: str) -> bool:
    """Check if a medication is an opioid."""
    normalized = normalize_drug_name(name)
    return normalized in OPIOIDS


def is_ppi(name: str) -> bool:
    """Check if a medication is a proton pump inhibitor."""
    normalized = normalize_drug_name(name)
    ppi_drugs = {"omeprazole", "pantoprazole", "lansoprazole", "esomeprazole", "rabeprazole", "dexlansoprazole"}
    return normalized in ppi_drugs


def is_anticoagulant(name: str) -> bool:
    """Check if a medication is an anticoagulant."""
    drug_info = get_drug_info(name)
    if drug_info and drug_info.is_anticoagulant:
        return True
    normalized = normalize_drug_name(name)
    return normalized in {"warfarin", "apixaban", "rivaroxaban", "enoxaparin", "heparin", "dabigatran", "edoxaban"}


def is_steroid_inhaler(name: str) -> bool:
    """Check if a medication is a steroid inhaler."""
    drug_info = get_drug_info(name)
    if drug_info and drug_info.is_steroid_inhaler:
        return True
    normalized = normalize_drug_name(name)
    steroid_inhalers = {"fluticasone-salmeterol", "budesonide-formoterol", "fluticasone",
                        "budesonide inhaler", "mometasone-formoterol"}
    return normalized in steroid_inhalers or any(k in normalized for k in ["advair", "symbicort", "flovent", "pulmicort", "dulera"])


def is_psychotropic(name: str) -> bool:
    """Check if a medication is a psychotropic."""
    drug_info = get_drug_info(name)
    if drug_info and drug_info.is_psychotropic:
        return True
    normalized = normalize_drug_name(name)
    return normalized in ANTIPSYCHOTICS or normalized in BENZODIAZEPINES or normalized in ANTIDEPRESSANTS


def is_antibiotic(name: str) -> bool:
    """Check if a medication is an antibiotic."""
    drug_info = get_drug_info(name)
    if drug_info and drug_info.is_antibiotic:
        return True
    normalized = normalize_drug_name(name)
    antibiotic_keywords = [
        "amoxicillin", "azithromycin", "ciprofloxacin", "levofloxacin", "doxycycline",
        "cephalexin", "metronidazole", "sulfamethoxazole", "trimethoprim", "nitrofurantoin",
        "clindamycin", "vancomycin", "ceftriaxone", "cefazolin", "augmentin",
        "piperacillin", "meropenem", "linezolid", "bactrim",
    ]
    return normalized in antibiotic_keywords or any(k in normalized for k in ["cillin", "mycin", "floxacin", "cef"])


def is_topical_steroid(name: str) -> bool:
    """Check if a medication is a topical steroid."""
    drug_info = get_drug_info(name)
    if drug_info and drug_info.is_topical_steroid:
        return True
    normalized = normalize_drug_name(name)
    return "topical" in normalized and any(k in normalized for k in ["triamcinolone", "betamethasone", "clobetasol", "hydrocortisone", "fluocinonide"])
