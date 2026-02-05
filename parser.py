"""Text parsing via Claude API for LTC medication reconciliation."""

import json
import re
from datetime import date, datetime
from typing import Any

from models import ParsedChart, Patient, Medication, LabResult
from config import get_anthropic_client, PARSING_MODEL
from drug_reference import normalize_drug_name, get_drug_info, FREQUENCY_MAP


PARSING_PROMPT = """You are a clinical data extraction assistant for a Long-Term Care (LTC) medication reconciliation system.

Your task is to parse copy-pasted EHR text and extract structured data. Follow these rules strictly:

## EXTRACTION RULES

1. **Medications**:
   - Extract ALL medications including scheduled, PRN, and supplements
   - Normalize brand names to generic (e.g., "Seroquel" → "quetiapine")
   - Normalize frequency abbreviations (e.g., "BID" → "twice daily", "QHS" → "at bedtime")
   - Extract dose, route, frequency, indication if present
   - Mark PRN medications with is_prn: true
   - If DEA schedule is mentioned (C-II, C-III, etc.), include it
   - Extract hold parameters if present (e.g., "hold for SBP <100")
   - Extract administration time if specified (e.g., "0800", "AM", "bedtime")
   - Extract formulation details (e.g., "ER", "XR", "SR", "succinate", "tartrate")
   - Extract stop date if documented
   - Extract last used/administered date for PRN medications if available

2. **Patient Information**:
   - Extract name, age, sex if available
   - Extract diagnoses/problem list
   - Extract allergies
   - Extract admission date if available
   - Extract date of birth (DOB) if available
   - Extract room number if available
   - Extract care center/unit/wing if available
   - Extract attending physician name if available
   - Extract psychiatrist name if available

3. **Labs**:
   - Extract lab results with values, units, dates, and flags (H/L/Critical)
   - Include reference ranges if shown

4. **Ambiguity Handling**:
   - If information is unclear or ambiguous, DO NOT guess
   - Add a note to parsing_notes explaining the ambiguity
   - Use null for fields you cannot determine
   - Set parsing_confidence lower (0.0-1.0) if data is unclear

5. **Duplicates**:
   - If the same medication appears multiple times with different doses/frequencies, include all entries
   - Add a parsing_note about potential duplicates

## OUTPUT FORMAT

Return a JSON object with this exact structure:
```json
{
  "patient": {
    "name": "string or null",
    "age": "integer or null",
    "sex": "string or null",
    "admission_date": "YYYY-MM-DD or null",
    "diagnoses": ["list of diagnoses"],
    "allergies": ["list of allergies"],
    "dob": "YYYY-MM-DD or null",
    "room": "string or null",
    "care_center": "string or null",
    "attending_physician": "string or null",
    "psychiatrist": "string or null"
  },
  "medications": [
    {
      "name": "generic name (normalized)",
      "brand": "brand name if different from generic",
      "dose": "dose string (e.g., '25 mg')",
      "route": "PO/IM/IV/topical/etc.",
      "frequency": "normalized frequency",
      "indication": "indication if documented",
      "start_date": "YYYY-MM-DD or null",
      "prescriber": "prescriber name or null",
      "is_prn": false,
      "schedule": "II/III/IV/V or null for DEA schedule",
      "last_used_date": "YYYY-MM-DD or null",
      "stop_date": "YYYY-MM-DD or null",
      "hold_parameters": "string or null (e.g., 'hold for SBP <100')",
      "administration_time": "string or null (e.g., '0800', 'AM', 'bedtime')",
      "formulation": "string or null (e.g., 'ER', 'XR', 'succinate', 'tartrate')",
      "duration_days": "integer or null (e.g., 14 for a 14-day antibiotic course)",
      "max_daily_dose": "string or null (e.g., '3,250 mg/24 hr')",
      "administration_instructions": "string or null (e.g., 'with 8oz water', 'rinse mouth after use')"
    }
  ],
  "labs": [
    {
      "test_name": "lab name",
      "value": "numeric value or null",
      "value_text": "text value if non-numeric",
      "unit": "unit string",
      "date": "YYYY-MM-DD or null",
      "reference_range": "range string",
      "flag": "H/L/Critical/null"
    }
  ],
  "parsing_confidence": 0.95,
  "parsing_notes": ["list of notes about parsing decisions or ambiguities"]
}
```

## POINTCLICKCARE (PCC) FORMAT GUIDANCE

If the input looks like a PCC Pharmacy Order Summary, follow these additional rules:

1. **Medication line format**: `Brand Form Dose (Generic Salt) Give [amount] via [route] [frequency] for [indication]`
   - The generic name is inside parentheses, may include salt form (e.g., "levetiracetam", "meropenem")
   - Strip salt suffixes from generic name (e.g., "atorvastatin calcium" -> "atorvastatin")
   - The "Give [amount]" is the actual administered dose (may differ from form dose)
   - Route follows "via" keyword (PO, G-Tube, IVPB, SubQ, Nebulization, Topical, etc.)

2. **Routes**: Normalize these PCC routes:
   - "G-Tube" -> "G-tube" (gastrostomy tube)
   - "IVPB" -> "IV" (IV piggyback)
   - "Nebulization" -> "nebulizer"
   - "Both Nostrils" -> "intranasal"
   - "Topically" -> "topical"

3. **Frequencies**: PCC uses natural language:
   - "2 Times a Day" -> "twice daily"
   - "3 Times a Day" -> "three times daily"
   - "Every 8 Hours" -> "every 8 hours"
   - "Every Night at Bedtime" -> "at bedtime"

4. **PRN entries**: Look for "PRN" keyword, and extract max dose if present (e.g., "Max 3,250 mg/24 hr")

5. **Hold parameters**: Extract text after "Hold for" (e.g., "Hold for SBP less than 100")

6. **Duration**: If a duration is mentioned (e.g., "for 14 days"), extract as duration_days

7. **Prescriber/NPI**: If NPI numbers or prescriber names appear, extract prescriber name

## IMPORTANT
- Return ONLY valid JSON, no other text
- Use null (not "null" string) for missing values
- Normalize all drug names to lowercase generic names
- Be conservative - if unsure, add to parsing_notes and reduce confidence"""


def parse_chart_text(text: str) -> ParsedChart:
    """Parse EHR text using Claude API."""
    if not text or not text.strip():
        return ParsedChart(
            parsing_confidence=0.0,
            parsing_notes=["Empty input text provided"]
        )

    client = get_anthropic_client()

    try:
        response = client.messages.create(
            model=PARSING_MODEL,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": f"{PARSING_PROMPT}\n\n---\n\nEHR TEXT TO PARSE:\n\n{text}"
                }
            ]
        )

        # Extract response text
        response_text = response.content[0].text

        # Parse JSON from response
        parsed_data = _extract_json(response_text)

        if not parsed_data:
            return ParsedChart(
                parsing_confidence=0.0,
                parsing_notes=["Failed to parse JSON from API response"]
            )

        # Convert to Pydantic models
        return _convert_to_models(parsed_data)

    except Exception as e:
        return ParsedChart(
            parsing_confidence=0.0,
            parsing_notes=[f"API error: {str(e)}"]
        )


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract JSON from response text."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _convert_to_models(data: dict[str, Any]) -> ParsedChart:
    """Convert parsed JSON to Pydantic models."""
    # Parse patient
    patient_data = data.get("patient", {})
    admission_date = _parse_date(patient_data.get("admission_date"))

    # Detect new admission (within 30 days)
    is_new_admission = False
    if admission_date:
        from config import NEW_ADMISSION_WINDOW_DAYS
        days_since = (date.today() - admission_date).days
        is_new_admission = days_since <= NEW_ADMISSION_WINDOW_DAYS

    patient = Patient(
        name=patient_data.get("name"),
        age=patient_data.get("age"),
        sex=patient_data.get("sex"),
        admission_date=admission_date,
        diagnoses=patient_data.get("diagnoses", []),
        allergies=patient_data.get("allergies", []),
        dob=_parse_date(patient_data.get("dob")),
        room=patient_data.get("room"),
        care_center=patient_data.get("care_center"),
        attending_physician=patient_data.get("attending_physician"),
        psychiatrist=patient_data.get("psychiatrist"),
        is_new_admission=is_new_admission,
    )

    # Parse medications
    medications = []
    for med_data in data.get("medications", []):
        name = med_data.get("name", "")
        normalized_name = normalize_drug_name(name)

        # Get drug info for additional data
        drug_info = get_drug_info(normalized_name)

        med = Medication(
            name=normalized_name,
            brand=med_data.get("brand"),
            dose=med_data.get("dose"),
            route=med_data.get("route"),
            frequency=_normalize_frequency(med_data.get("frequency")),
            indication=med_data.get("indication"),
            start_date=_parse_date(med_data.get("start_date")),
            prescriber=med_data.get("prescriber"),
            drug_class=drug_info.drug_class if drug_info else None,
            is_prn=med_data.get("is_prn", False),
            schedule=med_data.get("schedule") or (drug_info.dea_schedule if drug_info else None),
            last_used_date=_parse_date(med_data.get("last_used_date")),
            stop_date=_parse_date(med_data.get("stop_date")),
            hold_parameters=med_data.get("hold_parameters"),
            administration_time=med_data.get("administration_time"),
            formulation=med_data.get("formulation"),
            duration_days=med_data.get("duration_days"),
            max_daily_dose=med_data.get("max_daily_dose"),
            administration_instructions=med_data.get("administration_instructions"),
        )
        medications.append(med)

    # Parse labs
    labs = []
    for lab_data in data.get("labs", []):
        lab = LabResult(
            test_name=lab_data.get("test_name", ""),
            value=_parse_float(lab_data.get("value")),
            value_text=lab_data.get("value_text"),
            unit=lab_data.get("unit"),
            date=_parse_date(lab_data.get("date")),
            reference_range=lab_data.get("reference_range"),
            flag=lab_data.get("flag"),
        )
        labs.append(lab)

    return ParsedChart(
        patient=patient,
        medications=medications,
        labs=labs,
        parsing_confidence=data.get("parsing_confidence", 1.0),
        parsing_notes=data.get("parsing_notes", []),
    )


def _parse_date(date_str: str | None) -> date | None:
    """Parse date string to date object."""
    if not date_str:
        return None

    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


def _parse_float(value: Any) -> float | None:
    """Parse value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _normalize_frequency(freq: str | None) -> str | None:
    """Normalize medication frequency."""
    if not freq:
        return None

    freq_lower = freq.lower().strip()

    # Check direct mapping
    if freq_lower in FREQUENCY_MAP:
        return FREQUENCY_MAP[freq_lower]

    # Return original if no mapping found
    return freq
