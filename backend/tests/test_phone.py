"""
Phone normalization tests.

Covers all input formats, edge cases, and Unicode digit handling.
"""

import pytest
from app.utils.phone import normalize_phone


class TestNormalizePhoneExampleTable:
    """Test every row of the documented examples table."""

    def test_example_03001234567_raw(self):
        """03001234567 - raw mobile, no separator"""
        assert normalize_phone("03001234567") == "03001234567"

    def test_example_0300_dash_1234567(self):
        """0300-1234567 - mobile with dash"""
        assert normalize_phone("0300-1234567") == "03001234567"

    def test_example_0300_space_1234567(self):
        """0300 1234567 - mobile with space"""
        assert normalize_phone("0300 1234567") == "03001234567"

    def test_example_plus92_no_sep(self):
        """+923001234567 - international, no separator"""
        assert normalize_phone("+923001234567") == "03001234567"

    def test_example_plus92_with_spaces(self):
        """+92 300 1234567 - international with spaces"""
        assert normalize_phone("+92 300 1234567") == "03001234567"

    def test_example_92_no_plus(self):
        """923001234567 - country code without +"""
        assert normalize_phone("923001234567") == "03001234567"

    def test_example_042_landline(self):
        """042-35551234 - Lahore landline"""
        assert normalize_phone("042-35551234") == "04235551234"


class TestNormalizePhoneLandlineForms:
    """Test both complete and incomplete landline formats."""

    def test_lahore_complete(self):
        """Complete Lahore landline: 042-35551234"""
        assert normalize_phone("042-35551234") == "04235551234"

    def test_lahore_incomplete_no_area_code(self):
        """Incomplete Lahore landline: 35551234 (no city code 042)"""
        # No rule applies: not 10 digits starting with 3, so returned as-is
        assert normalize_phone("35551234") == "35551234"

    def test_karachi_complete(self):
        """Karachi landline: 021-..."""
        assert normalize_phone("021-1234567") == "0211234567"

    def test_rawalpindi_complete(self):
        """Rawalpindi landline: 051-..."""
        assert normalize_phone("051-1234567") == "0511234567"

    def test_peshawar_complete(self):
        """Peshawar landline: 091-..."""
        assert normalize_phone("091-2345678") == "0912345678"

    def test_quetta_complete(self):
        """Quetta landline: 081-..."""
        assert normalize_phone("081-2345678") == "0812345678"


class TestNormalizePhoneMixedCharacters:
    """Test input with non-digit characters mixed in."""

    def test_letters_mixed_in(self):
        """0300-abc-1234567 - letters mixed with digits"""
        # Letters are stripped, only "03001234567" remains
        assert normalize_phone("0300-abc-1234567") == "03001234567"

    def test_letters_and_symbols_mixed(self):
        """0300-a1b2c3-4567 - more complex mix"""
        assert normalize_phone("0300-a1b2c3-4567") == "03001234567"

    def test_only_letters(self):
        """abcdefghij - only letters, no digits"""
        assert normalize_phone("abcdefghij") == ""

    def test_only_symbols(self):
        """+-()-- - only symbols, no digits"""
        assert normalize_phone("+-()--") == ""


class TestNormalizePhoneEmptyInput:
    """Test empty and whitespace-only inputs."""

    def test_empty_string(self):
        """Empty string"""
        assert normalize_phone("") == ""

    def test_only_spaces(self):
        """Only whitespace"""
        assert normalize_phone("   ") == ""

    def test_tabs_and_newlines(self):
        """Only whitespace characters (tabs, newlines)"""
        assert normalize_phone("\t\n  \r") == ""

    def test_space_digit_space(self):
        """Spaces around digits (should trim and extract)"""
        assert normalize_phone("  03001234567  ") == "03001234567"


class TestNormalizePhoneInternationalPrefixes:
    """Test various international prefix formats."""

    def test_plus92_no_space(self):
        """+923001234567 - standard international format"""
        assert normalize_phone("+923001234567") == "03001234567"

    def test_plus92_spaces_after_plus(self):
        """+92 3001234567 - space after country code"""
        assert normalize_phone("+92 3001234567") == "03001234567"

    def test_plus92_spaces_everywhere(self):
        """+92 300 1234567 - multiple spaces"""
        assert normalize_phone("+92 300 1234567") == "03001234567"

    def test_plus92_dashes(self):
        """+92-300-1234567 - dashes instead of spaces"""
        assert normalize_phone("+92-300-1234567") == "03001234567"

    def test_plus92_mixed_separators(self):
        """+92 - 300-1234567 - mixed separators"""
        assert normalize_phone("+92 - 300-1234567") == "03001234567"

    def test_92_no_plus(self):
        """923001234567 - country code without +"""
        assert normalize_phone("923001234567") == "03001234567"

    def test_92_with_spaces(self):
        """92 300 1234567 - country code with spaces"""
        assert normalize_phone("92 300 1234567") == "03001234567"

    def test_0092_prefix(self):
        """00923001234567 - international dialling prefix (00) instead of +"""
        # 00 = international prefix (used in many countries)
        # Should normalize like +92
        assert normalize_phone("00923001234567") == "03001234567"

    def test_0092_with_spaces(self):
        """0092 300 1234567 - international prefix with spaces"""
        assert normalize_phone("0092 300 1234567") == "03001234567"


class TestNormalizePhoneTenDigitRule:
    """Test the 10-digit rule: exactly 10 digits + starts with 3 → prepend 0."""

    def test_10_digits_starts_with_3_mobile(self):
        """3001234567 - 10 digits, starts with 3 → becomes 03001234567"""
        # This is a mobile without leading 0
        assert normalize_phone("3001234567") == "03001234567"

    def test_10_digits_starts_with_3_with_dashes(self):
        """300-1234567 - 10 digits, starts with 3 with dashes"""
        assert normalize_phone("300-1234567") == "03001234567"

    def test_10_digits_starts_with_3_with_spaces(self):
        """300 1234567 - 10 digits, starts with 3 with spaces"""
        assert normalize_phone("300 1234567") == "03001234567"

    def test_10_digits_starts_with_1_landline(self):
        """1234567890 - 10 digits, starts with 1 (not 3) → no prepend"""
        # Rule doesn't apply: doesn't start with 3
        assert normalize_phone("1234567890") == "1234567890"

    def test_10_digits_starts_with_2_landline(self):
        """2123456789 - 10 digits, starts with 2 (not 3) → no prepend"""
        assert normalize_phone("2123456789") == "2123456789"

    def test_10_digits_starts_with_4_landline(self):
        """4123456789 - 10 digits, starts with 4 (not 3) → no prepend"""
        # A hypothetical landline starting with 4
        assert normalize_phone("4123456789") == "4123456789"

    def test_11_digits_starts_with_0_landline(self):
        """04235551234 - 11 digits, starts with 0 → rule doesn't apply"""
        # Lahore landline: 11 digits, doesn't match rule (rule needs exactly 10)
        assert normalize_phone("04235551234") == "04235551234"

    def test_11_digits_starts_with_03_mobile(self):
        """03001234567 - 11 digits, starts with 03 → rule doesn't apply"""
        # Already proper format; rule needs exactly 10, not 11
        assert normalize_phone("03001234567") == "03001234567"

    def test_9_digits_starts_with_3(self):
        """300123456 - 9 digits, starts with 3 → rule doesn't apply"""
        # Less than 10 digits
        assert normalize_phone("300123456") == "300123456"

    def test_12_digits_starts_with_3(self):
        """3001234567890 - 12 digits, starts with 3 → rule doesn't apply"""
        # More than 10 digits
        assert normalize_phone("3001234567890") == "3001234567890"


class TestNormalizePhoneUrduIndicDigits:
    """Test Urdu-Indic digit input (U+06F0–U+06F9)."""

    def test_urdu_indic_11_digits(self):
        """۰۳۰۰۱۲۳۴۵۶۷ - all Urdu-Indic digits"""
        # Should convert to ASCII equivalents
        assert normalize_phone("۰۳۰۰۱۲۳۴۵۶۷") == "03001234567"

    def test_urdu_indic_with_dashes(self):
        """۰۳۰۰-۱۲۳۴-۵۶۷ - Urdu-Indic with dashes"""
        assert normalize_phone("۰۳۰۰-۱۲۳۴-۵۶۷") == "03001234567"

    def test_urdu_indic_with_spaces(self):
        """۰۳۰۰ ۱۲۳۴ ۵۶۷ - Urdu-Indic with spaces"""
        assert normalize_phone("۰۳۰۰ ۱۲۳۴ ۵۶۷") == "03001234567"

    def test_urdu_indic_international(self):
        """+۹۲۳۰۰۱۲۳۴۵۶۷ - Urdu-Indic with international prefix"""
        assert normalize_phone("+۹۲۳۰۰۱۲۳۴۵۶۷") == "03001234567"

    def test_urdu_indic_country_code_only(self):
        """۹۲۳۰۰۱۲۳۴۵۶۷ - Urdu-Indic country code without +"""
        assert normalize_phone("۹۲۳۰۰۱۲۳۴۵۶۷") == "03001234567"

    def test_urdu_indic_10_digit_rule(self):
        """۳۰۰۱۲۳۴۵۶۷ - Urdu-Indic 10 digits starting with 3"""
        # Should apply 10-digit rule: 10 digits, starts with 3 → prepend 0
        assert normalize_phone("۳۰۰۱۲۳۴۵۶۷") == "03001234567"

    def test_mixed_ascii_and_urdu(self):
        """0300-۱۲۳۴-۵۶۷ - mixed ASCII and Urdu-Indic digits"""
        assert normalize_phone("0300-۱۲۳۴-۵۶۷") == "03001234567"


class TestNormalizePhoneReturnTypes:
    """Test return type consistency."""

    def test_return_is_string(self):
        """Return value is always a string"""
        result = normalize_phone("03001234567")
        assert isinstance(result, str)

    def test_empty_return_is_string(self):
        """Empty result is empty string, not None"""
        result = normalize_phone("")
        assert result == ""
        assert isinstance(result, str)

    def test_result_digits_only(self):
        """Result contains only ASCII digits"""
        result = normalize_phone("0300-1234567")
        assert all(c.isdigit() for c in result)

    def test_result_ascii_only(self):
        """Result contains only ASCII characters (0-9)"""
        result = normalize_phone("۰۳۰۰-۱۲۳۴-۵۶۷")
        # All characters should be ASCII 0-9
        assert result.encode("ascii") == result.encode("utf-8")


class TestNormalizePhoneEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_leading_plus_only(self):
        """+0300-1234567 - leading + on already local format"""
        # + is stripped, leaving 03001234567
        assert normalize_phone("+0300-1234567") == "03001234567"

    def test_multiple_plus_signs(self):
        """++923001234567 - multiple + signs"""
        # Both + stripped during digit extraction
        assert normalize_phone("++923001234567") == "03001234567"

    def test_multiple_zeros_at_start(self):
        """003001234567 - extra leading zeros"""
        # Not exactly 0092 pattern, just extra 0s
        # Result: "003001234567"
        assert normalize_phone("003001234567") == "003001234567"

    def test_parentheses_format(self):
        """(0300) 1234567 - parentheses format"""
        # Sometimes used: (area-code) number
        assert normalize_phone("(0300) 1234567") == "03001234567"

    def test_dots_as_separator(self):
        """0300.1234.567 - dots as separator"""
        assert normalize_phone("0300.1234.567") == "03001234567"

    def test_realistic_user_paste(self):
        """Realistic: user pastes from Urdu SMS with dashes and spaces"""
        # "۰۳۰۰  -  ۱۲۳۴  -  ۵۶۷۸" = ۰۳۰۰ + ۱۲۳۴ + ۵۶۷۸ = 12 Urdu digits
        assert normalize_phone("۰۳۰۰  -  ۱۲۳۴  -  ۵۶۷۸") == "030012345678"

    def test_foreign_number_us(self):
        """+1-202-5551234 - foreign number (US)"""
        # Accepted; US country code 1 becomes 01
        # "+1-202-5551234" → digits "12025551234"
        # Doesn't match 92 or 0092, starts with 1, not exactly 10 with 3
        # Result: "12025551234"
        assert normalize_phone("+1-202-5551234") == "12025551234"

    def test_zero_padding_mobile(self):
        """000300-1234567 - padded with zeros"""
        # Extra 00 at start: "000300" (6) + "1234567" (7) = 13 digits total
        assert normalize_phone("000300-1234567") == "0003001234567"
