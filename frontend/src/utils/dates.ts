/**
 * Date utilities for handling backend timestamps.
 * Backend sends naive UTC datetimes (via datetime.utcnow()) without timezone markers.
 * This module ensures consistent UTC parsing across the app.
 */

/**
 * Parse a backend timestamp (naive UTC datetime) into a Date object.
 * Backend sends strings like "2025-08-19T12:34:56" without a Z suffix.
 * Without correction, browsers parse these as LOCAL time, causing timezone errors.
 * This function appends Z if not present, ensuring UTC interpretation.
 * @param backendDateString ISO datetime string from the server (e.g., "2025-08-19T12:34:56")
 * @returns Date object parsed as UTC
 */
export function parseServerDate(backendDateString: string): Date {
  // Check if the string already ends with a timezone indicator: Z or ±HH:MM offset
  // Regex matches: Z at end, or +/-HH:MM at end (e.g., +05:00)
  const hasTimezone = /[Z]$|[+-]\d{2}:\d{2}$/.test(backendDateString);

  if (hasTimezone) {
    return new Date(backendDateString);
  }

  // Append Z to treat naive UTC datetime as UTC (not local time)
  return new Date(`${backendDateString}Z`);
}
