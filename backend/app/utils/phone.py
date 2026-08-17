"""
Phone number normalization utility.

Normalizes phone numbers to a canonical key format (0XXX..., ASCII digits only).
Handles multiple input formats and Unicode digit characters.

NORMALIZATION STRATEGY:
- Strip non-digit characters and spaces
- Convert any Unicode digit (including Urdu-Indic ۰–۹) to ASCII 0-9
  Reason: Users in Pakistan may type on Urdu keyboard, producing U+06F0–U+06F9
  (Urdu-Indic digits). These pass isdigit() but don't match ASCII key searches.
  Using int(c, 10) converts any Unicode digit to ASCII equivalent.
- Normalize country codes: +92, 92, 0092 all become local 0 prefix
- Apply 10-digit rule: if exactly 10 digits AND starts with 3, prepend 0
  Reason: Converts mobile without leading 0 (3001234567) to proper format
  (03001234567). Importantly, does NOT fire for landlines—a Lahore landline
  like 042-35551234 is 11 digits after stripping, so the rule never applies
  to it. This prevents accidentally prefixing valid landlines that start
  with something other than 3.

RETURN VALUE: Empty string if input has no digits, otherwise normalized key.
"""

import unicodedata


def normalize_phone(raw: str) -> str:
    """
    Normalize a phone number to a canonical key (0XXX format, ASCII digits only).

    Args:
        raw: Raw phone number as typed (may include spaces, dashes, +, country code,
             or Urdu-Indic digits from Urdu keyboard input)

    Returns:
        Normalized key: digits only, starts with 0, in ASCII (0-9).
        Returns empty string if input has no digits.

    Examples:
        normalize_phone("03001234567") → "03001234567"
        normalize_phone("0300-1234567") → "03001234567"
        normalize_phone("3001234567") → "03001234567"  (10 digits, starts with 3)
        normalize_phone("+923001234567") → "03001234567"
        normalize_phone("923001234567") → "03001234567"
        normalize_phone("00923001234567") → "03001234567"  (00 prefix like +)
        normalize_phone("042-35551234") → "04235551234"  (11 digits, no rule)
        normalize_phone("35551234") → "35551234"  (8 digits, incomplete, no rule)
        normalize_phone("۰۳۰۰۱۲۳۴۵۶۷") → "03001234567"  (Urdu-Indic digits)
        normalize_phone("") → ""
        normalize_phone("   ") → ""
    """
    if not raw or not isinstance(raw, str):
        return ""

    # Trim whitespace
    raw = raw.strip()

    if not raw:
        return ""

    # Extract digits: convert any Unicode digit to ASCII 0-9
    # This handles both ASCII (0-9) and Urdu-Indic (۰-۹, U+06F0–U+06F9)
    digits = "".join(str(int(c, 10)) if c.isdigit() else "" for c in raw)

    if not digits:
        return ""

    # Normalize international prefixes
    # "00923001234567" → "03001234567" (00 is international dialling prefix)
    if digits.startswith("0092"):
        digits = "0" + digits[4:]
    # "+923001234567" or "923001234567" → "03001234567"
    elif digits.startswith("92"):
        digits = "0" + digits[2:]
    # Already starts with 0 (local format)

    # Apply 10-digit rule: if exactly 10 digits AND starts with 3, prepend 0
    # This handles: "3001234567" (10 digits, mobile without leading 0) → "03001234567"
    # Does NOT apply to landlines like "04235551234" (11 digits) or "0421234567" (10 digits, starts with 0)
    if len(digits) == 10 and digits[0] == "3":
        digits = "0" + digits

    return digits
