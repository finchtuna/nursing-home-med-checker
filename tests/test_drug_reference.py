"""Unit tests for drug reference database improvements."""

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from drug_reference import (
    normalize_drug_name,
    get_drug_info,
    is_bowel_medication,
    is_antibiotic,
    is_anticoagulant,
    FREQUENCY_MAP,
)


class TestSaltFormStripping:
    """Test salt-form normalization in normalize_drug_name()."""

    def test_atorvastatin_calcium(self):
        assert normalize_drug_name("atorvastatin calcium") == "atorvastatin"

    def test_pantoprazole_sodium(self):
        assert normalize_drug_name("pantoprazole sodium") == "pantoprazole"

    def test_metformin_hydrochloride(self):
        assert normalize_drug_name("metformin hydrochloride") == "metformin"

    def test_enoxaparin_sodium(self):
        assert normalize_drug_name("enoxaparin sodium") == "enoxaparin"

    def test_ferrous_sulfate_stays(self):
        """ferrous sulfate is a full drug name, should NOT be stripped."""
        assert normalize_drug_name("ferrous sulfate") == "ferrous sulfate"

    def test_already_generic(self):
        assert normalize_drug_name("levetiracetam") == "levetiracetam"

    def test_brand_name(self):
        assert normalize_drug_name("Keppra") == "levetiracetam"

    def test_case_insensitive(self):
        assert normalize_drug_name("ATORVASTATIN CALCIUM") == "atorvastatin"


class TestNewDrugs:
    """Test that new drugs are in the database and return correct info."""

    def test_levetiracetam(self):
        info = get_drug_info("levetiracetam")
        assert info is not None
        assert info.drug_class == "anticonvulsant"
        assert info.therapeutic_category == "anticonvulsant"
        assert "drug level" in info.required_labs

    def test_meropenem(self):
        info = get_drug_info("meropenem")
        assert info is not None
        assert info.is_antibiotic is True
        assert info.drug_class == "carbapenem antibiotic"

    def test_glycopyrrolate(self):
        info = get_drug_info("glycopyrrolate")
        assert info is not None
        assert info.is_anticholinergic is True
        assert info.anticholinergic_burden == 2

    def test_ondansetron(self):
        info = get_drug_info("ondansetron")
        assert info is not None
        assert info.is_qtc_prolonging is True

    def test_acetaminophen(self):
        info = get_drug_info("acetaminophen")
        assert info is not None
        assert info.drug_class == "analgesic"

    def test_albuterol(self):
        info = get_drug_info("albuterol")
        assert info is not None
        assert info.therapeutic_category == "respiratory"

    def test_ipratropium_albuterol(self):
        info = get_drug_info("ipratropium-albuterol")
        assert info is not None
        assert info.is_anticholinergic is True

    def test_ferrous_sulfate(self):
        info = get_drug_info("ferrous sulfate")
        assert info is not None
        assert info.drug_class == "iron supplement"

    def test_magnesium_hydroxide(self):
        info = get_drug_info("magnesium hydroxide")
        assert info is not None
        assert info.drug_class == "antacid/laxative"

    def test_nystatin(self):
        info = get_drug_info("nystatin")
        assert info is not None
        assert info.drug_class == "antifungal"

    def test_miconazole(self):
        info = get_drug_info("miconazole")
        assert info is not None

    def test_enoxaparin(self):
        info = get_drug_info("enoxaparin")
        assert info is not None
        assert info.is_anticoagulant is True
        assert info.is_fall_risk is True

    def test_phenytoin(self):
        info = get_drug_info("phenytoin")
        assert info is not None
        assert "phenytoin level" in info.required_labs
        assert info.is_fall_risk is True

    def test_guaifenesin(self):
        info = get_drug_info("guaifenesin")
        assert info is not None
        assert info.therapeutic_category == "respiratory"

    def test_zinc_oxide(self):
        info = get_drug_info("zinc oxide")
        assert info is not None
        assert info.therapeutic_category == "dermatological"


class TestBowelMedication:
    """Test is_bowel_medication with new entries."""

    def test_magnesium_hydroxide_is_bowel(self):
        assert is_bowel_medication("magnesium hydroxide") is True

    def test_milk_of_magnesia_is_bowel(self):
        assert is_bowel_medication("milk of magnesia") is True

    def test_docusate_still_works(self):
        assert is_bowel_medication("docusate") is True

    def test_senna_still_works(self):
        assert is_bowel_medication("senna") is True

    def test_non_bowel_med(self):
        assert is_bowel_medication("lisinopril") is False


class TestAntibioticCheck:
    """Test is_antibiotic with new entries."""

    def test_meropenem_is_antibiotic(self):
        assert is_antibiotic("meropenem") is True

    def test_amoxicillin_still_works(self):
        assert is_antibiotic("amoxicillin") is True

    def test_non_antibiotic(self):
        assert is_antibiotic("lisinopril") is False


class TestAnticoagulantCheck:
    """Test is_anticoagulant with new entries."""

    def test_enoxaparin_is_anticoagulant(self):
        assert is_anticoagulant("enoxaparin") is True

    def test_warfarin_still_works(self):
        assert is_anticoagulant("warfarin") is True

    def test_apixaban_still_works(self):
        assert is_anticoagulant("apixaban") is True

    def test_non_anticoagulant(self):
        assert is_anticoagulant("lisinopril") is False


class TestFrequencyMap:
    """Test PCC natural-language frequency normalizations."""

    def test_2_times_a_day(self):
        assert FREQUENCY_MAP["2 times a day"] == "twice daily"

    def test_3_times_a_day(self):
        assert FREQUENCY_MAP["3 times a day"] == "three times daily"

    def test_4_times_a_day(self):
        assert FREQUENCY_MAP["4 times a day"] == "four times daily"

    def test_every_8_hours(self):
        assert FREQUENCY_MAP["every 8 hours"] == "every 8 hours"

    def test_every_6_hours(self):
        assert FREQUENCY_MAP["every 6 hours"] == "every 6 hours"

    def test_once_a_day(self):
        assert FREQUENCY_MAP["once a day"] == "daily"

    def test_every_night_at_bedtime(self):
        assert FREQUENCY_MAP["every night at bedtime"] == "at bedtime"

    def test_every_morning(self):
        assert FREQUENCY_MAP["every morning"] == "every morning"

    def test_every_evening(self):
        assert FREQUENCY_MAP["every evening"] == "every evening"

    def test_original_bid_still_works(self):
        assert FREQUENCY_MAP["bid"] == "twice daily"

    def test_original_qhs_still_works(self):
        assert FREQUENCY_MAP["qhs"] == "at bedtime"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
