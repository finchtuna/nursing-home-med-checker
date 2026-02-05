# Nursing Home Medication Checker

**A tool that helps pharmacists catch medication problems in nursing home patients.**

Pharmacists who work with nursing homes have to review dozens of patient medication lists every month. This tool makes that job faster and safer by automatically flagging potential issues like:

- **Dangerous drug combinations** (like mixing opioids with sedatives)
- **Medications that are risky for elderly patients** (Beers Criteria)
- **Missing lab tests** (like INR checks for blood thinners)
- **Too many "fall risk" medications** together
- **Antipsychotic compliance issues** (important for CMS regulations)

## How It Works

1. **Paste** messy medication data from any electronic health record
2. **AI parses** the unstructured text into clean data
3. **Rules engine** checks for 50+ clinical issues
4. **Get a report** with prioritized findings and recommendations

![Demo Screenshot](docs/screenshot.png)

## Quick Start

### 1. Install Python requirements
```bash
pip install -r requirements.txt
```

### 2. Set your API key
```bash
# Windows
set ANTHROPIC_API_KEY=your-key-here

# Mac/Linux
export ANTHROPIC_API_KEY=your-key-here
```

Get a key at: https://console.anthropic.com/settings/keys

### 3. Run the web demo
```bash
python web_demo.py
```

Then open http://localhost:5000 in your browser.

## What It Checks For

| Category | What It Finds |
|----------|---------------|
| **Drug Interactions** | Serotonin syndrome risk, QTc prolongation, excessive sedation |
| **Beers Criteria** | Medications to avoid in patients 65+ |
| **Fall Risk** | Flags when 3+ fall-risk meds are combined |
| **Lab Monitoring** | Missing or overdue labs (INR, HbA1c, kidney function, etc.) |
| **Antipsychotics** | GDR requirements, black box warnings, inappropriate use |
| **Controlled Substances** | Opioid + benzo combinations, PRN patterns |

## Example Output

```
HIGH PRIORITY FLAGS
-------------------
[CONTROLLED_SUBSTANCE]
  Finding: Concurrent opioid and benzodiazepine therapy (FDA Black Box Warning)
  Action: Avoid concurrent use if possible. Use lowest effective doses.

[FALL_RISK]
  Finding: Elevated fall risk: 5 fall-risk medications
  Action: Review medications, consider alternatives or enhanced precautions.

[BEERS_CRITERIA]
  Finding: Beers Criteria: diphenhydramine (avoid)
  Action: Consider alternatives. Document rationale if continued.
```

## Project Structure

```
ltc-medrec/
├── web_demo.py        # Web interface (easiest way to use)
├── medrec.py          # Command-line interface
├── parser.py          # AI text parsing
├── analyzer.py        # Clinical rules engine
├── drug_reference.py  # Medication database (80+ drugs)
├── note_generator.py  # Report generation
├── models.py          # Data structures
└── tests/             # Test files and sample data
```

## Command Line Usage

```bash
# Interactive mode - paste text directly
python medrec.py

# From a file
python medrec.py --input patient_chart.txt

# Quick flags-only report
python medrec.py --input chart.txt --flags-only

# Save output to file
python medrec.py --input chart.txt -o report.txt
```

## Technical Details

- **AI Parsing**: Uses Claude API to extract structured data from messy EHR text
- **Rules Engine**: Deterministic Python logic (not AI) for auditable, consistent results
- **Drug Database**: Curated reference with Beers criteria, interactions, monitoring requirements

## Disclaimer

This tool assists with medication reviews but does not replace clinical judgment. All recommendations should be evaluated by a qualified healthcare professional. Final prescribing decisions rest with the attending physician.

## License

MIT License - feel free to use and modify.
