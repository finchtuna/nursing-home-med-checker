"""Simple web demo for LTC medication reconciliation."""

import os
import sys

# Check for API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Please set your ANTHROPIC_API_KEY environment variable first:")
    print("  set ANTHROPIC_API_KEY=your-key-here")
    sys.exit(1)

from flask import Flask, render_template_string, request
from parser import parse_chart_text
from analyzer import analyze_medications
from note_generator import generate_clinical_note, generate_flags_only_report, generate_diana_style_report

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>LTC Medication Reconciliation Tool</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        @media (max-width: 900px) {
            .container { grid-template-columns: 1fr; }
        }
        .panel {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        textarea {
            width: 100%;
            height: 400px;
            font-family: monospace;
            font-size: 13px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            background: #3498db;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 10px;
        }
        button:hover { background: #2980b9; }
        button:disabled { background: #bdc3c7; cursor: not-allowed; }
        .output {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 4px;
            white-space: pre-wrap;
            font-family: monospace;
            font-size: 12px;
            max-height: 600px;
            overflow-y: auto;
        }
        .loading {
            display: none;
            color: #e67e22;
            font-weight: bold;
            margin-top: 10px;
        }
        .sample-btn {
            background: #27ae60;
            font-size: 14px;
            padding: 8px 16px;
            margin-right: 10px;
        }
        .sample-btn:hover { background: #219a52; }
        h2 { color: #34495e; margin-top: 0; }
        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 5px;
        }
        .badge-high { background: #e74c3c; color: white; }
        .badge-medium { background: #f39c12; color: white; }
        .badge-low { background: #3498db; color: white; }
        .stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        .stat-box {
            background: #ecf0f1;
            padding: 10px;
            border-radius: 4px;
            text-align: center;
        }
        .stat-number { font-size: 24px; font-weight: bold; color: #2c3e50; }
        .stat-label { font-size: 12px; color: #7f8c8d; }
    </style>
</head>
<body>
    <h1>🏥 LTC Medication Reconciliation Tool</h1>
    <p>Paste EHR text below to analyze medication regimens for clinical issues.</p>

    <div style="margin-bottom: 15px;">
        <button class="sample-btn" onclick="loadSample('tabular')">Load Sample: Tabular Format</button>
        <button class="sample-btn" onclick="loadSample('narrative')">Load Sample: Narrative Format</button>
        <button class="sample-btn" onclick="loadSample('pcc')">Load Sample: PCC Format</button>
    </div>

    <div class="container">
        <div class="panel">
            <h2>📋 Input: EHR Text</h2>
            <form method="POST" id="analyzeForm">
                <textarea name="ehr_text" id="ehrText" placeholder="Paste EHR medication list, MAR, or progress note here...">{{ input_text or '' }}</textarea>
                <br>
                <div style="margin: 10px 0; padding: 10px; background: #ecf0f1; border-radius: 4px;">
                    <strong>Output Format:</strong><br>
                    <label style="margin-right: 15px;"><input type="radio" name="output_format" value="flags" {{ 'checked' if output_format == 'flags' else '' }}> Flags Only</label>
                    <label style="margin-right: 15px;"><input type="radio" name="output_format" value="diana" {{ 'checked' if (output_format or 'diana') == 'diana' else '' }}> Diana-Style Notes</label>
                    <label><input type="radio" name="output_format" value="narrative" {{ 'checked' if output_format == 'narrative' else '' }}> Full Narrative</label>
                    <br><br>
                    <label>Pharmacist Name: <input type="text" name="pharmacist_name" value="{{ pharmacist_name or 'Consultant Pharmacist' }}" style="padding: 4px; border: 1px solid #ddd; border-radius: 3px; width: 200px;"></label>
                </div>
                <button type="submit" id="submitBtn">🔍 Analyze Medications</button>
                <span class="loading" id="loading">⏳ Analyzing... (this takes 10-20 seconds)</span>
            </form>
        </div>

        <div class="panel">
            <h2>📊 Analysis Results</h2>
            {% if result %}
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{{ stats.total_meds }}</div>
                    <div class="stat-label">Medications</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number" style="color: #e74c3c;">{{ stats.high_flags }}</div>
                    <div class="stat-label">High Priority</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{{ stats.complexity }}</div>
                    <div class="stat-label">Complexity</div>
                </div>
            </div>
            <div class="output">{{ result }}</div>
            {% else %}
            <p style="color: #7f8c8d;">Results will appear here after analysis...</p>
            {% endif %}
        </div>
    </div>

    <script>
        const samples = {
            tabular: `MEDICATION ADMINISTRATION RECORD
================================
Patient: Smith, Margaret
DOB: 03/15/1942  Age: 82  Sex: Female
Room: 204-B

DIAGNOSES: Alzheimer's dementia, Major depressive disorder,
Type 2 diabetes, Hypertension, Atrial fibrillation

ALLERGIES: Penicillin (rash), Sulfa drugs

CURRENT MEDICATIONS
-------------------
Quetiapine 100 mg PO BID - Agitation
Sertraline 100 mg PO daily - Depression
Lorazepam 0.5 mg PO QHS PRN - Anxiety
Metformin 500 mg PO BID - Diabetes
Warfarin 5 mg PO daily - AFib
Omeprazole 20 mg PO daily - GERD

LABS (01/15/2024):
INR 2.8, K 4.2, Cr 1.4 (H), Glucose 142 (H)`,

            narrative: `Progress Note - Mrs. Davis is an 88-year-old female with
major depressive disorder, anxiety, chronic pain, and hypertension.
She was admitted following a fall with hip fracture.

Allergies: Codeine (nausea), Aspirin (GI bleed)

Current medications:
- Mirtazapine 30 mg at bedtime for depression
- Alprazolam 0.25 mg twice daily for anxiety
- Oxycodone 5 mg every 6 hours PRN for pain
- Omeprazole 40 mg daily for GERD
- Lisinopril 20 mg daily for BP

Labs from 01/15/2024: K 3.3 (low), Cr 0.9
Nursing notes patient has been drowsy and had 2 near-falls.`,

            pcc: `PointClickCare - Pharmacy Order Summary
Patient: Johnson, Robert
DOB: 06/22/1938  Age: 87  Sex: Male
Room: 312-A  Unit: Skilled Nursing
Attending: Dr. Martinez, NPI: 1234567890

Diagnoses: Seizure disorder, Pneumonia, GERD, Hypertension,
Type 2 Diabetes, Anemia, Chronic pain

Allergies: Sulfa (rash), Latex

ACTIVE MEDICATION ORDERS
========================
Keppra Tab 500 MG (levetiracetam) Give 500 MG via G-Tube 2 Times a Day for Seizure Disorder
Merrem IV Soln 500 MG/20ML (meropenem) Give 500 MG via IVPB Every 8 Hours for Infection - for 14 days
Tylenol Tab 325 MG (acetaminophen) Give 650 MG via G-Tube Every 6 Hours PRN for Pain - Max 3,250 mg/24 hr
Protonix Tab 40 MG (pantoprazole sodium) Give 40 MG via G-Tube Once a Day for GERD
Lopressor Tab 50 MG (metoprolol tartrate) Give 50 MG via G-Tube 2 Times a Day for Hypertension Hold for SBP less than 100 or HR less than 60
Lipitor Tab 40 MG (atorvastatin calcium) Give 40 MG via G-Tube Every Night at Bedtime for Hyperlipidemia
Glucophage Tab 500 MG (metformin hydrochloride) Give 500 MG via G-Tube 2 Times a Day for Diabetes
DuoNeb Soln (ipratropium-albuterol) Give 3 ML via Nebulization Every 6 Hours for COPD
Feosol Tab 325 MG (ferrous sulfate) Give 325 MG via G-Tube Once a Day for Anemia
Lovenox Inj 40 MG/0.4ML (enoxaparin sodium) Give 40 MG via SubQ Once a Day for DVT Prophylaxis
Zofran ODT 4 MG (ondansetron) Give 4 MG via G-Tube Every 8 Hours PRN for Nausea
Milk of Magnesia Susp (magnesium hydroxide) Give 30 ML via G-Tube Once a Day PRN for Constipation
Nystatin Oral Susp 100000 Unit/ML (nystatin) Give 5 ML Swish and Spit 4 Times a Day for Thrush`
        };

        function loadSample(type) {
            document.getElementById('ehrText').value = samples[type];
        }

        document.getElementById('analyzeForm').onsubmit = function() {
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('loading').style.display = 'inline';
        };
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    input_text = None
    stats = {}
    output_format = "diana"
    pharmacist_name = "Consultant Pharmacist"

    if request.method == "POST":
        input_text = request.form.get("ehr_text", "")
        output_format = request.form.get("output_format", "flags")
        pharmacist_name = request.form.get("pharmacist_name", "Consultant Pharmacist")

        if input_text.strip():
            try:
                # Parse the text
                parsed = parse_chart_text(input_text)

                # Analyze
                analysis = analyze_medications(parsed)

                # Generate report based on selected format
                if output_format == "diana":
                    result = generate_diana_style_report(parsed, analysis, pharmacist_name)
                elif output_format == "narrative":
                    result = generate_clinical_note(parsed, analysis)
                else:
                    result = generate_flags_only_report(parsed, analysis)

                # Stats for display
                stats = {
                    "total_meds": analysis.total_medications,
                    "high_flags": sum(1 for f in analysis.flags if f.severity.value == "HIGH"),
                    "complexity": analysis.complexity_level.value,
                }
            except Exception as e:
                result = f"Error: {str(e)}"
                stats = {"total_meds": 0, "high_flags": 0, "complexity": "N/A"}

    return render_template_string(
        HTML_TEMPLATE,
        result=result,
        input_text=input_text,
        stats=stats,
        output_format=output_format,
        pharmacist_name=pharmacist_name,
    )


if __name__ == "__main__":
    print("\n" + "="*50)
    print("LTC Medication Reconciliation Demo")
    print("="*50)
    print("\nOpen this link in your browser:\n")
    print("   http://localhost:5000")
    print("\nShare this with your friend!")
    print("(You'll need to keep this window open)")
    print("\nPress Ctrl+C to stop the server")
    print("="*50 + "\n")

    app.run(debug=False, host="0.0.0.0", port=5000)
