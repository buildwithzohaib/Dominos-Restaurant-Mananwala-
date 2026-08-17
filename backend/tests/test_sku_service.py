"""
Tests for SKU generation service (Task 2.5)

Tests only the pure build_sku() function — no database, no fixtures.
"""

import pytest
from app.services.sku_service import build_sku


class TestBuildSku:
    """Tests for deterministic SKU generation."""

    def test_normal_case_chicken_nuggets_in_fast_food(self):
        """
        Standard case: Chicken Nuggets in Fast Food category.

        Derivation:
        - Category: "Fast Food" → name_key="fastfood" → first 3 chars "fas" → "FAS"
        - Product: "Chicken Nuggets" → name_key="chickennuggets" → first 3 chars "chi" → "CHI"
        - Sequence: 001 (no collision)
        - Expected: FAS-CHI-001
        """
        sku = build_sku(
            category_name_key="fastfood",
            product_name_key="chickennuggets",
            category_id=1,
            taken=set()
        )
        assert sku == "FAS-CHI-001"

    def test_second_product_same_prefix_increments_to_002(self):
        """
        Second product with same category and abbr prefix — sequence increments.

        Derivation:
        - Category prefix: "FAS" (from "fastfood")
        - Product 1: "Chicken Nuggets" → "CHI" → "FAS-CHI-001" (already in taken)
        - Product 2: "Chilli Sauce" → name_key="chillisauce" → first 3 "chi" → "CHI"
        - Collision on "FAS-CHI-001", so try "FAS-CHI-002" → available
        - Expected: FAS-CHI-002
        """
        sku = build_sku(
            category_name_key="fastfood",
            product_name_key="chillisauce",
            category_id=1,
            taken={"FAS-CHI-001"}
        )
        assert sku == "FAS-CHI-002"

    def test_third_product_same_prefix_increments_to_003(self):
        """
        Third product collides twice and increments to 003.

        Both "FAS-CHI-001" and "FAS-CHI-002" are taken,
        so the third product gets "FAS-CHI-003".
        """
        sku = build_sku(
            category_name_key="fastfood",
            product_name_key="chickenpops",  # name_key="chickenpops" → "CHI"
            category_id=1,
            taken={"FAS-CHI-001", "FAS-CHI-002"}
        )
        assert sku == "FAS-CHI-003"

    def test_product_name_with_fewer_than_3_letters_7up(self):
        """
        Product name shorter than 3 characters — use available characters.

        Derivation:
        - "7Up" → name_key="7up"
        - First 3 chars of "7up" are "7up" (all 3 present) → "7UP"
        - Digits are valid alphanumeric characters
        - Category: "Drinks" → "DRI"
        - Expected: DRI-7UP-001
        """
        sku = build_sku(
            category_name_key="drinks",
            product_name_key="7up",
            category_id=3,
            taken=set()
        )
        assert sku == "DRI-7UP-001"

    def test_single_letter_product_name(self):
        """
        Product with only 1 letter name — use what is available.

        Derivation:
        - "A" → name_key="a"
        - First 3 chars available: just "a" → "A" (no padding)
        - Expected: DRI-A-001
        """
        sku = build_sku(
            category_name_key="drinks",
            product_name_key="a",
            category_id=3,
            taken=set()
        )
        assert sku == "DRI-A-001"

    def test_two_letter_product_name(self):
        """
        Product with 2 letter name — use both.

        Derivation:
        - "AB" → name_key="ab"
        - First 3 chars available: "ab" → "AB"
        - Expected: DRI-AB-001
        """
        sku = build_sku(
            category_name_key="drinks",
            product_name_key="ab",
            category_id=3,
            taken=set()
        )
        assert sku == "DRI-AB-001"

    def test_non_ascii_product_name_falls_back_to_gen(self):
        """
        Product with no ASCII letters (e.g., Urdu) falls back to GEN.

        Derivation:
        - Product: "چکن رول" → name_key="" (no ASCII after normalization)
        - Fallback: "GEN"
        - Category: "Drinks" → "DRI"
        - Expected: DRI-GEN-001
        """
        sku = build_sku(
            category_name_key="drinks",
            product_name_key="",  # Simulates non-ASCII name with no ASCII letters
            category_id=3,
            taken=set()
        )
        assert sku == "DRI-GEN-001"

    def test_non_ascii_product_collision_increments_gen(self):
        """
        Second non-ASCII product in same category — GEN sequence increments.

        Both products lack ASCII in their names, so both get GEN prefix.
        Collision on "DRI-GEN-001", so second gets "DRI-GEN-002".
        """
        sku = build_sku(
            category_name_key="drinks",
            product_name_key="",
            category_id=3,
            taken={"DRI-GEN-001"}
        )
        assert sku == "DRI-GEN-002"

    def test_non_ascii_category_uses_id_fallback(self):
        """
        Non-ASCII category name falls back to C{id:02d}.

        Derivation:
        - Category: "فاسٹ فوڈ" (Fast Food, id=5) → name_key="" (no ASCII)
          → Fallback: "C05"
        - Product: "Chicken" → name_key="chicken" → "CHI"
        - Expected: C05-CHI-001
        """
        sku = build_sku(
            category_name_key="",  # Non-ASCII category with no ASCII letters
            product_name_key="chicken",
            category_id=5,
            taken=set()
        )
        assert sku == "C05-CHI-001"

    def test_non_ascii_category_and_product_both_fallback(self):
        """
        Both category and product names are non-ASCII.

        Derivation:
        - Category: "فاسٹ فوڈ" (id=5) → "C05"
        - Product: "چکن رول" → "GEN"
        - Expected: C05-GEN-001
        """
        sku = build_sku(
            category_name_key="",
            product_name_key="",
            category_id=5,
            taken=set()
        )
        assert sku == "C05-GEN-001"

    def test_regular_name_various_categories(self):
        """
        Standard cases with different categories.

        Pepsi in Drinks (category_id=3) → DRI-PEP-001
        Fries in Fast Food (category_id=1) → FAS-FRY-001
        """
        sku1 = build_sku(
            category_name_key="drinks",
            product_name_key="pepsi",
            category_id=3,
            taken=set()
        )
        assert sku1 == "DRI-PEP-001"

        sku2 = build_sku(
            category_name_key="fastfood",
            product_name_key="regularfries",
            category_id=1,
            taken=set()
        )
        assert sku2 == "FAS-REG-001"

    def test_long_collision_sequence(self):
        """
        Many collisions in sequence (e.g., 001 through 010).

        Simulates a category with many products sharing the same prefix.
        """
        taken = {f"DRI-PEP-{i:03d}" for i in range(1, 11)}  # 001-010 taken
        sku = build_sku(
            category_name_key="drinks",
            product_name_key="pepsi",
            category_id=3,
            taken=taken
        )
        assert sku == "DRI-PEP-011"

    def test_category_with_short_name(self):
        """
        Category name shorter than 3 characters.

        Derivation:
        - "AB" (hypothetical 2-letter category) → name_key="ab" → first 3 "ab" → "AB"
        - Expected: AB-CHI-001
        """
        sku = build_sku(
            category_name_key="ab",
            product_name_key="chicken",
            category_id=7,
            taken=set()
        )
        assert sku == "AB-CHI-001"

    def test_mixed_case_and_symbols_in_name_key(self):
        """
        name_key is already lowercase alphanumeric (no spaces/symbols),
        so this tests the normal path. Included for completeness.

        Derivation:
        - "zingerfriesddrink" (normalized name_key) → "ZIN"
        - "deals" → "DEA"
        - Expected: DEA-ZIN-001
        """
        sku = build_sku(
            category_name_key="deals",
            product_name_key="zingerfriesddrink",
            category_id=2,
            taken=set()
        )
        assert sku == "DEA-ZIN-001"

    def test_numeric_leading_name(self):
        """
        Product name starting with digits (e.g., "7Up", "3D Lay's").

        Derivation:
        - "3dlay" → first 3 "3dl" → "3DL"
        - "snacks" → "SNA"
        - Expected: SNA-3DL-001
        """
        sku = build_sku(
            category_name_key="snacks",
            product_name_key="3dlay",
            category_id=4,
            taken=set()
        )
        assert sku == "SNA-3DL-001"

    def test_empty_taken_set(self):
        """
        Empty taken set — all SKUs are available (no collisions).
        """
        sku = build_sku(
            category_name_key="fastfood",
            product_name_key="chickennuggets",
            category_id=1,
            taken=set()
        )
        assert sku == "FAS-CHI-001"

    def test_mixed_script_product_name_ascii_second(self):
        """
        Mixed Urdu and ASCII name where ASCII part comes second.

        Derivation:
        - Product: "چکن Roll" → name_key="چکنroll" (via derive_key)
        - _derive_prefix filters ASCII from whole string: "roll" → "ROL"
        - Category: "Drinks" → "DRI"
        - Expected: DRI-ROL-001

        This tests the undocumented but beneficial behaviour where
        _derive_prefix extracts ASCII characters from anywhere in the string,
        not just the start. A mixed-script name with ASCII content yields
        the ASCII part, not a GEN fallback.
        """
        sku = build_sku(
            category_name_key="drinks",
            product_name_key="چکنroll",  # Urdu + ASCII, ASCII comes second
            category_id=3,
            taken=set()
        )
        assert sku == "DRI-ROL-001"

    def test_mixed_script_product_name_single_ascii_letter(self):
        """
        Mixed Urdu and ASCII name where ASCII part is a single letter.

        Derivation:
        - Product: "چکنx" → name_key="چکنx" (via derive_key)
        - _derive_prefix filters ASCII from whole string: "x" → "X" (1 char available)
        - Category: "Drinks" → "DRI"
        - Expected: DRI-X-001

        Tests edge case: a product with mixed script and minimal ASCII content.
        The single letter is extracted and used, not treated as "too short".
        """
        sku = build_sku(
            category_name_key="drinks",
            product_name_key="چکنx",  # Urdu + single ASCII letter
            category_id=3,
            taken=set()
        )
        assert sku == "DRI-X-001"

    def test_collision_avoidance_with_large_taken_set(self):
        """
        Ensure collision loop works with a large existing set.

        Creates a set of 100 SKUs and verifies the function finds the first free slot.

        Derivation:
        - Category: "category" → "CAT"
        - Product: "abbreviation" → name_key="abbreviation" → first 3 "abb" → "ABB"
        - Taken: CAT-ABB-001 through CAT-ABB-100
        - Expected: CAT-ABB-101 (first available after the 100)
        """
        taken = {f"CAT-ABB-{i:03d}" for i in range(1, 101)}  # 001-100 taken
        sku = build_sku(
            category_name_key="category",
            product_name_key="abbreviation",
            category_id=1,
            taken=taken
        )
        assert sku == "CAT-ABB-101"
