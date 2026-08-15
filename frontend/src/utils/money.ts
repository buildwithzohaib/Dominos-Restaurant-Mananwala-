/**
 * Money utilities for paisa (integer) handling.
 * 1 rupee = 100 paisa. All internal values are integers (paisa).
 */

const CURRENCY_SYMBOL = "Rs. ";

/**
 * Format a number with South Asian grouping: last 3 digits, then groups of 2.
 * Example: 1234567 -> "12,34,567"
 */
export function formatSouthAsianGrouping(num: number): string {
  if (num === 0) return "0";

  const str = Math.abs(num).toString();

  if (str.length <= 3) {
    return str;
  }

  // Split into: last 3 digits and everything before
  const lastThree = str.slice(-3);
  const beforeLastThree = str.slice(0, -3);

  // Group the "before" part in pairs from right to left
  const pairs: string[] = [];
  for (let i = beforeLastThree.length; i > 0; i -= 2) {
    const start = Math.max(0, i - 2);
    pairs.unshift(beforeLastThree.slice(start, i));
  }

  return pairs.concat([lastThree]).join(",");
}

/**
 * Format paisa as a currency string.
 * Handles null/undefined as "Rs. 0".
 * Decimal part: either 0 digits (if paisa % 100 === 0) or exactly 2 (zero-padded).
 * Example: 125000 -> "Rs. 1,250"
 * Example: 45050 -> "Rs. 450.50"
 * Example: 45005 -> "Rs. 450.05"
 */
export function formatMoney(paisa: number | null | undefined): string {
  if (paisa === null || paisa === undefined) {
    return CURRENCY_SYMBOL + "0";
  }

  const isNegative = paisa < 0;
  const absPaisa = Math.abs(paisa);

  const rupees = Math.floor(absPaisa / 100);
  const remainder = absPaisa % 100;

  const rupeesFormatted = formatSouthAsianGrouping(rupees);

  let result: string;
  if (remainder === 0) {
    result = rupeesFormatted;
  } else {
    const decimalPart = String(remainder).padStart(2, "0");
    result = `${rupeesFormatted}.${decimalPart}`;
  }

  if (isNegative) {
    result = `-${result}`;
  }

  return CURRENCY_SYMBOL + result;
}

/**
 * Convert rupees (decimal user input) to paisa (integer).
 * Example: 450.50 -> 45050
 */
export function rupeesToPaisa(rupees: number): number {
  return Math.round(rupees * 100);
}

/**
 * Convert paisa (integer) to rupees (decimal for display/forms).
 * Example: 45050 -> 450.5
 */
export function paisaToRupees(paisa: number): number {
  return paisa / 100;
}
