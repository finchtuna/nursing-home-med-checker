"""Unit tests for text parser."""

import pytest
from datetime import date

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import _parse_date, _normalize_frequency, _extract_json, _convert_to_models
from drug_reference import normalize_drug_name, get_drug_info


class TestDrugNormalization:
    """Tests for drug name normalization."""

    def test_brand_to_generic(self):
        """Brand names should normalize to generic."""
        assert normalize_drug_name("Seroquel") == "quetiapine"
        assert normalize_drug_name("Ativan") == "lorazepam"
        assert normalize_drug_name("Zoloft") == "sertraline"

    def test_generic_unchanged(self):
        """Generic names should remain unchanged."""
        assert normalize_drug_name("quetiapine") == "quetiapine"
        assert normalize_drug_name("lorazepam") == "lorazepam"

    def test_case_insensitive(self):
        """Normalization should be case-insensitive."""
        assert normalize_drug_name("SEROQUEL") == "quetiapine"
        assert normalize_drug_name("seroquel") == "quetiapine"
        assert normalize_drug_name("Seroquel") == "quetiapine"

    def test_extended_release_brands(self):
        """Extended release formulations should normalize."""
        assert normalize_drug_name("Seroquel XR") == "quetiapine"
        assert normalize_drug_name("Effexor XR") == "venlafaxine"

    def test_unknown_drug_returns_lowercase(self):
        """Unknown drugs should return lowercase original."""
        assert normalize_drug_name("unknowndrug") == "unknowndrug"
        assert normalize_drug_name("SomeBrandNotListed") == "somebrandnotlisted"


class TestDrugInfo:
    """Tests for drug info retrieval."""

    def test_get_drug_info_by_generic(self):
        """Should retrieve drug info by generic name."""
        info = get_drug_info("quetiapine")
        assert info is not None
        assert info.generic_name == "quetiapine"
        assert info.is_beers_list is True
        assert info.requires_gdr is True

    def test_get_drug_info_by_brand(self):
        """Should retrieve drug info by brand name."""
        info = get_drug_info("Seroquel")
        assert info is not None
        assert info.generic_name == "quetiapine"

    def test_get_drug_info_unknown_returns_none(self):
        """Unknown drugs should return None."""
        info = get_drug_info("unknowndrug123")
        assert info is None


class TestFrequencyNormalization:
    """Tests for frequency normalization."""

    def test_common_abbreviations(self):
        """Common abbreviations should normalize."""
        assert _normalize_frequency("qd") == "daily"
        assert _normalize_frequency("bid") == "twice daily"
        assert _normalize_frequency("tid") == "three times daily"
        assert _normalize_frequency("qhs") == "at bedtime"
        assert _normalize_frequency("prn") == "as needed"

    def test_case_insensitive(self):
        """Normalization should be case-insensitive."""
        assert _normalize_frequency("QD") == "daily"
        assert _normalize_frequency("BID") == "twice daily"

    def test_unknown_frequency_unchanged(self):
        """Unknown frequencies should remain unchanged."""
        assert _normalize_frequency("every 6 hours") == "every 6 hours"
        assert _normalize_frequency("twice a day with meals") == "twice a day with meals"

    def test_none_returns_none(self):
        """None input should return None."""
        assert _normalize_frequency(None) is None


class TestDateParsing:
    """Tests for date parsing."""

    def test_iso_format(self):
        """ISO format should parse."""
        assert _parse_date("2024-01-15") == date(2024, 1, 15)

    def test_us_format(self):
        """US format should parse."""
        assert _parse_date("01/15/2024") == date(2024, 1, 15)
        assert _parse_date("1/5/24") == date(2024, 1, 5)

    def test_none_returns_none(self):
        """None input should return None."""
        assert _parse_date(None) is None

    def test_invalid_returns_none(self):
        """Invalid date should return None."""
        assert _parse_date("not a date") is None
        assert _parse_date("2024-13-45") is None


class TestJsonExtraction:
    """Tests for JSON extraction from response text."""

    def test_plain_json(self):
        """Plain JSON should extract."""
        text = '{"patient": {"name": "Test"}, "medications": []}'
        result = _extract_json(text)
        assert result is not None
        assert result["patient"]["name"] == "Test"

    def test_json_in_markdown(self):
        """JSON in markdown code block should extract."""
        text = '''Here's the parsed data:
```json
{"patient": {"name": "Test"}, "medications": []}
```
'''
        result = _extract_json(text)
        assert result is not None
        assert result["patient"]["name"] == "Test"

    def test_json_with_surrounding_text(self):
        """JSON with surrounding text should extract."""
        text = 'Here is the result: {"patient": {"name": "Test"}} end'
        result = _extract_json(text)
        assert result is not None
        assert result["patient"]["name"] == "Test"

    def test_invalid_json_returns_none(self):
        """Invalid JSON should return None."""
        text = "This is not JSON at all"
        result = _extract_json(text)
        assert result is None


class TestModelConversion:
    """Tests for converting parsed JSON to Pydantic models."""

    def test_basic_conversion(self):
        """Basic data should convert to models."""
        data = {
            "patient": {
                "name": "John Doe",
                "age": 75,
                "diagnoses": ["hypertension", "diabetes"],
                "allergies": ["penicillin"]
            },
            "medications": [
                {
                    "name": "lisinopril",
                    "dose": "10 mg",
                    "frequency": "daily",
                    "is_prn": False
                }
            ],
            "labs": [
                {
                    "test_name": "BMP",
                    "date": "2024-01-15"
                }
            ],
            "parsing_confidence": 0.95,
            "parsing_notes": []
        }

        result = _convert_to_models(data)

        assert result.patient.name == "John Doe"
        assert result.patient.age == 75
        assert len(result.medications) == 1
        assert result.medications[0].name == "lisinopril"
        assert len(result.labs) == 1
        assert result.parsing_confidence == 0.95

    def test_brand_name_normalization(self):
        """Brand names should be normalized during conversion."""
        data = {
            "patient": {},
            "medications": [
                {"name": "Seroquel", "dose": "25 mg"}
            ],
            "labs": [],
            "parsing_confidence": 1.0,
            "parsing_notes": []
        }

        result = _convert_to_models(data)

        assert result.medications[0].name == "quetiapine"

    def test_missing_fields_use_defaults(self):
        """Missing fields should use defaults."""
        data = {
            "medications": [{"name": "lisinopril"}],
            "parsing_confidence": 0.8
        }

        result = _convert_to_models(data)

        assert result.patient.name is None
        assert result.patient.age is None
        assert result.patient.diagnoses == []
        assert len(result.medications) == 1
        assert result.labs == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
