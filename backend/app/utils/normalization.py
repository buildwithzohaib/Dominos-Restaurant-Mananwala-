"""
Text normalization for products and categories (Rule 9).

Three forms of each name:
- name_raw: Exactly as typed, unchanged. Preserved for audit/history.
- name_display: Whitespace-normalized only; preserves case and punctuation.
             Used for all UI display (screens, receipts, dropdowns).
- name_key: Lowercase, alphanumeric only; used for duplicate detection.

NFC unicode normalization is applied to all derived forms so that
decomposed and composed characters (e.g., "é" as U+00E9 vs U+0065+U+0301)
produce identical keys.
"""

import unicodedata
import re


def normalize_display(text: str) -> str:
    """
    Normalize text for display.

    Steps:
    1. Apply NFC unicode normalization (handles decomposed characters)
    2. Strip leading/trailing whitespace
    3. Collapse internal whitespace runs to single space

    Preserves original case and punctuation; only normalizes whitespace
    and unicode encoding.

    Args:
        text: Raw input (may have extra whitespace, decomposed chars)

    Returns:
        Normalized display form

    Examples:
        "  BBQ  Chicken  " → "BBQ Chicken"
        "café" (decomposed) → "café" (composed, consistent encoding)
        "zinger + fries + drink" → "zinger + fries + drink"
        "MCDONALD'S" → "MCDONALD'S" (case preserved)
        "iPhone case" → "iPhone case" (case preserved)
    """
    # Apply NFC normalization first
    normalized = unicodedata.normalize('NFC', text)

    # Strip leading/trailing whitespace
    stripped = normalized.strip()

    # Collapse internal whitespace runs to single space
    collapsed = re.sub(r'\s+', ' ', stripped)

    return collapsed


def derive_key(text: str) -> str:
    """
    Derive a deduplication key from text.

    Steps:
    1. Apply NFC unicode normalization to the input
    2. Apply NFD and remove combining marks only after ASCII letters (diacritic folding for Latin)
    3. Recompose with NFC to restore characters that were decomposed but not folded
    4. Lowercase and keep only alphanumeric characters

    Two different typings of the same product (e.g., "7up" vs "7 Up" or "café" vs "cafe")
    produce the same key, catching duplicates.

    Diacritic folding applies to Latin characters only: "café" becomes "cafe", matching
    "cafe". Combining marks after non-ASCII characters (Urdu, Arabic, etc.) are preserved
    and recomposed so "ئ" (decomposed as "ي" + hamza) is reassembled and survives as "ئ".
    This ensures that composed and decomposed Urdu/Arabic input produce identical keys.

    Args:
        text: Raw input (may have extra whitespace, punctuation, case, diacritics, decomposed)

    Returns:
        Lowercase alphanumeric key with Latin diacritics folded, Urdu/Arabic combined
        characters preserved. Empty string if no alphanumeric characters remain.

    Examples:
        "7up" → "7up"
        "7 Up" → "7up" (whitespace removed)
        "500ml" → "500ml"
        "500 ml" → "500ml" (space removed)
        "Coke 1L" → "coke1l"
        "Coke 1 L" → "coke1l" (space removed)
        "MCDONALD'S" → "mcdonalds" (case lowered, apostrophe removed)
        "café" (composed U+00E9) → "cafe" (diacritics folded)
        "café" (decomposed U+0065+U+0301) → "cafe" (same key, diacritics folded)
        "CAFÉ" → "cafe" (case lowered, diacritics folded)
        "ئ" (composed, U+0626) → "ئ" (preserved)
        NFD("ئ") (decomposed as U+064A+U+0654) → "ئ" (recomposed, same key)
        "+++" → "" (empty, should be rejected)
        "   " → "" (empty, should be rejected)
        "résumé" → "resume" (Latin diacritics folded)
    """
    # Step 1: Apply NFC normalization to the input
    normalized = unicodedata.normalize('NFC', text)

    # Step 2: Apply NFD and fold diacritics for Latin text only
    nfd = unicodedata.normalize('NFD', normalized)

    result = []
    for char in nfd:
        # Check if this is a combining mark (diacritic)
        is_combining_mark = unicodedata.category(char) == 'Mn'

        # Check if previous character was ASCII and alphabetic (Latin letter)
        prev_is_ascii_letter = (
            result and
            ord(result[-1]) < 128 and
            result[-1].isalpha()
        )

        # Skip combining marks after ASCII letters (diacritic folding for Latin only)
        # Preserve combining marks after non-ASCII characters (Urdu, Arabic, etc.)
        if is_combining_mark and prev_is_ascii_letter:
            continue

        result.append(char)

    folded = ''.join(result)

    # Step 3: Recompose everything that was not folded
    # This restores "ي" + hamza → "ئ" while keeping "cafe" (folded Latin)
    recomposed = unicodedata.normalize('NFC', folded)

    # Step 4: Lowercase and keep only alphanumeric characters
    lowered = recomposed.lower()
    key = ''.join(c for c in lowered if c.isalnum())

    return key


def normalize_name(raw: str) -> tuple[str, str, str]:
    """
    Normalize a name into three forms (Rule 9 pattern).

    Args:
        raw: Name as typed by user (may have extra whitespace, mixed case, etc.)

    Returns:
        Tuple of (name_raw, name_display, name_key)
        - name_raw: exactly as typed, trimmed only
        - name_display: whitespace-normalized, case preserved
        - name_key: lowercase, alphanumeric only, deduplicated

    Raises:
        ValueError: if name_raw is empty (only whitespace)
    """
    name_raw = raw.strip() if raw else ""

    if not name_raw:
        raise ValueError("Name cannot be empty or only whitespace")

    name_display = normalize_display(name_raw)
    name_key = derive_key(name_raw)

    return (name_raw, name_display, name_key)
