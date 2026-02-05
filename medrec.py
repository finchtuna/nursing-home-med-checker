#!/usr/bin/env python3
"""CLI entrypoint for LTC medication reconciliation tool."""

import sys
import click
from pathlib import Path

from models import ParsedChart
from parser import parse_chart_text
from analyzer import analyze_medications
from note_generator import generate_clinical_note, generate_flags_only_report, generate_diana_style_report


@click.command()
@click.option(
    "--input", "-i", "input_file",
    type=click.Path(exists=True, path_type=Path),
    help="Input file containing EHR text to parse"
)
@click.option(
    "--meds", "meds_file",
    type=click.Path(exists=True, path_type=Path),
    help="Separate file containing medications list"
)
@click.option(
    "--labs", "labs_file",
    type=click.Path(exists=True, path_type=Path),
    help="Separate file containing lab results"
)
@click.option(
    "--stdin", "use_stdin",
    is_flag=True,
    help="Read input from stdin (for piping)"
)
@click.option(
    "--output", "-o", "output_file",
    type=click.Path(path_type=Path),
    help="Output file for the clinical note"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose output with debug information"
)
@click.option(
    "--flags-only", "flags_only",
    is_flag=True,
    help="Generate flags report only, skip narrative generation"
)
@click.option(
    "--diana-style", "diana_style",
    is_flag=True,
    help="Generate Diana-style consultant pharmacist workup report"
)
@click.option(
    "--pharmacist-name", "pharmacist_name",
    default="Consultant Pharmacist",
    help="Pharmacist name for Diana-style report signature line"
)
def main(
    input_file: Path | None,
    meds_file: Path | None,
    labs_file: Path | None,
    use_stdin: bool,
    output_file: Path | None,
    verbose: bool,
    flags_only: bool,
    diana_style: bool,
    pharmacist_name: str,
):
    """LTC Medication Reconciliation Tool

    Parses EHR text, performs clinical analysis, and generates medication review notes.

    \b
    Usage modes:
      medrec.py                    Interactive mode (paste text, double-Enter to finish)
      medrec.py --input FILE       Read from file
      medrec.py --stdin            Read from stdin (for piping)
      medrec.py --meds M --labs L  Separate files for meds and labs

    \b
    Examples:
      python medrec.py --input patient_chart.txt
      python medrec.py --input chart.txt --flags-only
      python medrec.py --input chart.txt --diana-style
      python medrec.py --input chart.txt --diana-style --pharmacist-name "Diana Lu"
      python medrec.py --input chart.txt -o review.txt
      cat chart.txt | python medrec.py --stdin
    """
    try:
        # Get input text
        text = _get_input_text(input_file, meds_file, labs_file, use_stdin, verbose)

        if not text or not text.strip():
            click.echo("Error: No input text provided.", err=True)
            sys.exit(1)

        if verbose:
            click.echo(f"Input text length: {len(text)} characters")
            click.echo("-" * 40)

        # Parse the text
        click.echo("Parsing EHR text...")
        parsed = parse_chart_text(text)

        if verbose:
            _print_parsed_summary(parsed)

        if parsed.parsing_confidence < 0.5:
            click.echo(
                f"Warning: Low parsing confidence ({parsed.parsing_confidence:.0%}). "
                "Results may be incomplete.",
                err=True
            )
            for note in parsed.parsing_notes:
                click.echo(f"  - {note}", err=True)

        # Analyze medications
        click.echo("Analyzing medication regimen...")
        analysis = analyze_medications(parsed)

        if verbose:
            _print_analysis_summary(analysis)

        # Generate output
        if diana_style:
            click.echo("Generating Diana-style consultant pharmacist report...")
            output = generate_diana_style_report(parsed, analysis, pharmacist_name)
        elif flags_only:
            click.echo("Generating flags report...")
            output = generate_flags_only_report(parsed, analysis)
        else:
            click.echo("Generating clinical note...")
            output = generate_clinical_note(parsed, analysis)

        # Output results
        if output_file:
            output_file.write_text(output, encoding="utf-8")
            click.echo(f"Note saved to: {output_file}")
        else:
            click.echo("\n" + "=" * 60)
            click.echo(output)

    except ValueError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nCancelled.", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _get_input_text(
    input_file: Path | None,
    meds_file: Path | None,
    labs_file: Path | None,
    use_stdin: bool,
    verbose: bool
) -> str:
    """Get input text from various sources."""

    # Stdin mode
    if use_stdin:
        if verbose:
            click.echo("Reading from stdin...")
        return sys.stdin.read()

    # File input mode
    if input_file:
        if verbose:
            click.echo(f"Reading from file: {input_file}")
        return input_file.read_text(encoding="utf-8")

    # Separate meds/labs files
    if meds_file or labs_file:
        parts = []
        if meds_file:
            if verbose:
                click.echo(f"Reading medications from: {meds_file}")
            parts.append("MEDICATIONS:\n" + meds_file.read_text(encoding="utf-8"))
        if labs_file:
            if verbose:
                click.echo(f"Reading labs from: {labs_file}")
            parts.append("LABS:\n" + labs_file.read_text(encoding="utf-8"))
        return "\n\n".join(parts)

    # Interactive mode
    return _interactive_input()


def _interactive_input() -> str:
    """Get input interactively with multi-line support."""
    click.echo("=" * 60)
    click.echo("LTC Medication Reconciliation Tool")
    click.echo("=" * 60)
    click.echo()
    click.echo("Paste your EHR text below.")
    click.echo("Press Enter twice (blank line) when finished.")
    click.echo("-" * 40)

    lines = []
    blank_count = 0

    try:
        while True:
            line = input()
            if line == "":
                blank_count += 1
                if blank_count >= 2:
                    break
                lines.append(line)
            else:
                blank_count = 0
                lines.append(line)
    except EOFError:
        pass

    return "\n".join(lines).strip()


def _print_parsed_summary(parsed: ParsedChart):
    """Print summary of parsed data."""
    click.echo()
    click.echo("-" * 40)
    click.echo("PARSED DATA SUMMARY")
    click.echo("-" * 40)

    patient = parsed.patient
    click.echo(f"Patient: {patient.name or 'Unknown'}")
    click.echo(f"Age: {patient.age or 'Unknown'}")
    click.echo(f"Diagnoses: {len(patient.diagnoses)}")
    click.echo(f"Allergies: {len(patient.allergies)}")
    click.echo(f"Medications: {len(parsed.medications)}")
    click.echo(f"Labs: {len(parsed.labs)}")
    click.echo(f"Parsing confidence: {parsed.parsing_confidence:.0%}")

    if parsed.parsing_notes:
        click.echo("Notes:")
        for note in parsed.parsing_notes:
            click.echo(f"  - {note}")

    click.echo("-" * 40)


def _print_analysis_summary(analysis):
    """Print summary of analysis results."""
    click.echo()
    click.echo("-" * 40)
    click.echo("ANALYSIS SUMMARY")
    click.echo("-" * 40)

    click.echo(f"Complexity: {analysis.complexity_level.value} (Score: {analysis.complexity_score})")
    click.echo(f"Total flags: {len(analysis.flags)}")

    high_count = sum(1 for f in analysis.flags if f.severity.value == "HIGH")
    medium_count = sum(1 for f in analysis.flags if f.severity.value == "MEDIUM")
    low_count = sum(1 for f in analysis.flags if f.severity.value == "LOW")

    click.echo(f"  HIGH: {high_count}")
    click.echo(f"  MEDIUM: {medium_count}")
    click.echo(f"  LOW: {low_count}")

    click.echo()
    click.echo(f"Fall risk meds: {analysis.fall_risk_count}")
    click.echo(f"CNS depressants: {analysis.cns_depressant_count}")
    click.echo(f"Anticholinergics: {analysis.anticholinergic_count}")
    click.echo(f"Controlled substances: {analysis.controlled_substance_count}")
    click.echo(f"Antipsychotics: {analysis.antipsychotic_count}")
    click.echo(f"Beers list: {analysis.beers_count}")

    click.echo("-" * 40)


if __name__ == "__main__":
    main()
