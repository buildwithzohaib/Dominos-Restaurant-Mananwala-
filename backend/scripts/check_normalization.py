#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test normalization functions with Urdu and Latin text.
Verifies that:
1. Latin diacritics are folded (café → cafe)
2. Urdu/Arabic composed vs decomposed produce identical keys
3. Combining marks are preserved and recomposed for non-Latin text
"""

import sys
import os
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.normalization import derive_key, normalize_display

# Basic test cases
cases = [
    "café",
    "cafe",
    "CAFÉ",
    "زنجر + فرائز + ڈرنک",
    "ڈرنک",
    "چکن نگٹس",
    "7 Up",
    "500 ml",
    "Coke 1 L",
    "MCDONALD'S",
    "+++",
    "   ",
    "Zinger + Fries + Drink",
    "zinger",
]

print("=" * 120)
print("BASIC TESTS")
print("=" * 120)
print("Input (repr) -> derive_key (repr) | normalize_display (repr)")
print("-" * 120)

for s in cases:
    key = derive_key(s)
    display = normalize_display(s)
    print(f"{repr(s):45} -> {repr(key):35} | {repr(display)}")

# Critical verification tests
print("\n" + "=" * 120)
print("CRITICAL VERIFICATION TESTS")
print("=" * 120)

print("\n1. Latin diacritics folding must stay True:")
print(f"   café == cafe: {derive_key('café') == derive_key('cafe')}")

print("\n2. Urdu: composed vs decomposed must produce identical keys:")
composed = "ئ"  # U+0626 (ARABIC LETTER YEH WITH HAMZA ABOVE)
decomposed = unicodedata.normalize("NFD", composed)
print(f"   Composed length: {len(composed)}, Decomposed length: {len(decomposed)}")
print(f"   derive_key(composed): {repr(derive_key(composed))}")
print(f"   derive_key(decomposed): {repr(derive_key(decomposed))}")
print(f"   Keys match: {derive_key(composed) == derive_key(decomposed)}")
print(f"   Key contains 'ئ' (preserved): {'ئ' in derive_key(composed)}")

print("\n3. Full Urdu string: composed vs decomposed must produce identical keys:")
s_composed = "زنجر + فرائز + ڈرنک"
s_decomposed = unicodedata.normalize("NFD", s_composed)
key_composed = derive_key(s_composed)
key_decomposed = derive_key(s_decomposed)
print(f"   Composed input: {repr(s_composed)}")
print(f"   Decomposed input: {repr(s_decomposed)}")
print(f"   Key from composed: {repr(key_composed)}")
print(f"   Key from decomposed: {repr(key_decomposed)}")
print(f"   Keys match: {key_composed == key_decomposed}")
print(f"   Key contains 'ئ': {'ئ' in key_composed}")
