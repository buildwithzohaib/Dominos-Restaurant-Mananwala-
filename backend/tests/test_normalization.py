# -*- coding: utf-8 -*-
"""
Unit tests for text normalization (Rule 9).
Tests normalization of product and category names, collision detection,
diacritic folding for Latin, and preservation of Urdu/Arabic text.
"""

import unicodedata
import pytest

from app.utils.normalization import derive_key, normalize_display


class TestDeriveKeyExistingData:
    """Test derive_key with existing products and categories."""

    def test_five_product_names(self):
        """Existing product names produce their expected keys."""
        assert derive_key("Chicken Nuggets") == "chickennuggets"
        assert derive_key("Regular Fries") == "regularfries"
        assert derive_key("Zinger + Fries + Drink") == "zingerfriesdrink"
        assert derive_key("Pepsi") == "pepsi"
        assert derive_key("zinger") == "zinger"

    def test_three_category_names(self):
        """Existing category names produce their expected keys."""
        assert derive_key("Fast Food") == "fastfood"
        assert derive_key("Deals") == "deals"
        assert derive_key("Drinks") == "drinks"

    def test_existing_data_no_collisions(self):
        """All existing product and category keys are distinct."""
        keys = [
            derive_key("Chicken Nuggets"),
            derive_key("Regular Fries"),
            derive_key("Zinger + Fries + Drink"),
            derive_key("Pepsi"),
            derive_key("zinger"),
            derive_key("Fast Food"),
            derive_key("Deals"),
            derive_key("Drinks"),
        ]
        assert len(keys) == len(set(keys)), f"Collision detected: {keys}"


class TestDeriveKeyCollisions:
    """Test that intended collisions (formatting variations) match."""

    def test_collision_7up_spacing(self):
        """Numbers with spacing must collide: 7up == 7 Up."""
        assert derive_key("7up") == derive_key("7 Up")

    def test_collision_500ml_spacing(self):
        """Units with spacing must collide: 500ml == 500 ml."""
        assert derive_key("500ml") == derive_key("500 ml")

    def test_collision_coke_spacing(self):
        """Mixed numbers and spacing must collide: Coke 1L == Coke 1 L."""
        assert derive_key("Coke 1L") == derive_key("Coke 1 L")

    def test_collision_symbols_spacing(self):
        """Symbol variations must collide: Zinger + Fries == Zinger Fries."""
        assert derive_key("Zinger + Fries + Drink") == derive_key(
            "Zinger Fries Drink"
        )

    def test_non_collision_zinger_variations(self):
        """Distinct products must NOT collide: zinger != zingerburger."""
        assert derive_key("zinger") != derive_key("zingerburger")

    def test_non_collision_pepsi_variations(self):
        """Distinct products must NOT collide: pepsi != pepsimax."""
        assert derive_key("pepsi") != derive_key("pepsimax")


class TestDeriveKeyLatinDiacritics:
    """Test that Latin diacritics are folded consistently."""

    def test_latin_diacritics_cafe(self):
        """Accented café folds to unaccented cafe."""
        assert derive_key("café") == derive_key("cafe")

    def test_latin_diacritics_uppercase(self):
        """Uppercase accented CAFÉ folds to cafe."""
        assert derive_key("CAFÉ") == derive_key("cafe")

    def test_latin_diacritics_resume(self):
        """Multiple accents: résumé folds to resume."""
        assert derive_key("résumé") == derive_key("resume")


class TestDeriveKeyUrdu:
    """Test that Urdu text handles composition/decomposition correctly."""

    def test_urdu_composed_vs_decomposed(self):
        """Urdu composed ئ (U+0626) vs decomposed ي+hamza must produce identical keys."""
        composed = "ئ"  # U+0626 ARABIC LETTER YEH WITH HAMZA ABOVE
        decomposed = unicodedata.normalize("NFD", composed)
        # Verify decomposed is longer (decomposed into base + combining mark)
        assert len(decomposed) > len(composed)
        # Keys must match
        assert derive_key(composed) == derive_key(decomposed)

    def test_urdu_codepoint_preserved(self):
        """Urdu key must contain U+0626 (composed), not U+064A (decomposed base)."""
        composed = "ئ"  # U+0626
        key = derive_key(composed)
        # Key must contain the composed character
        assert "ئ" in key
        # Verify the exact codepoint is U+0626
        assert ord(key[0]) == 0x0626

    def test_urdu_full_string_composed_vs_decomposed(self):
        """Full Urdu string composed vs decomposed input must match."""
        urdu_string = "زنجر + فرائز + ڈرنک"
        urdu_decomposed = unicodedata.normalize("NFD", urdu_string)
        assert derive_key(urdu_string) == derive_key(urdu_decomposed)

    def test_urdu_full_string_expected_key(self):
        """Full Urdu string produces expected key with all letters intact."""
        urdu_string = "زنجر + فرائز + ڈرنک"
        expected_key = "زنجرفرائزڈرنک"
        assert derive_key(urdu_string) == expected_key


class TestDeriveKeyEdgeCases:
    """Test edge cases: empty keys, case normalization."""

    def test_symbols_only_empty(self):
        """Symbols only (+++) produce empty key."""
        assert derive_key("+++") == ""

    def test_whitespace_only_empty(self):
        """Whitespace only produce empty key."""
        assert derive_key("   ") == ""

    def test_empty_string_empty(self):
        """Empty string produces empty key."""
        assert derive_key("") == ""

    def test_mixed_symbols_whitespace_empty(self):
        """Mixed symbols and whitespace produce empty key."""
        assert derive_key("++  ..  ++") == ""

    def test_case_uppercase_to_lowercase(self):
        """Uppercase PEPSI normalizes to pepsi."""
        assert derive_key("PEPSI") == derive_key("pepsi")

    def test_case_mixed_to_lowercase(self):
        """Mixed case PePsI normalizes to pepsi."""
        assert derive_key("PePsI") == derive_key("pepsi")


class TestNormalizeDisplay:
    """Test normalize_display: whitespace normalization and case/punctuation preservation."""

    def test_trim_and_collapse_whitespace(self):
        """Leading/trailing trimmed, internal runs collapsed to single space."""
        assert normalize_display("  BBQ   Chicken  ") == "BBQ Chicken"

    def test_preserve_uppercase(self):
        """Uppercase letters preserved."""
        assert normalize_display("MCDONALD'S") == "MCDONALD'S"

    def test_preserve_mixed_case(self):
        """Mixed case preserved."""
        assert normalize_display("iPhone case") == "iPhone case"

    def test_preserve_punctuation(self):
        """Punctuation and symbols preserved."""
        assert (
            normalize_display("Zinger + Fries + Drink")
            == "Zinger + Fries + Drink"
        )

    def test_urdu_text_visually_unchanged(self):
        """Urdu text output matches input exactly."""
        urdu_text = "زنجر + فرائز + ڈرنک"
        assert normalize_display(urdu_text) == urdu_text

    def test_whitespace_only_becomes_empty(self):
        """Whitespace-only input becomes empty string."""
        assert normalize_display("   ") == ""
