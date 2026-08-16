/**
 * Derive the first letter of the restaurant name for the sidebar badge.
 * Returns empty string if settings not loaded or name is empty/whitespace.
 */
export const getRestaurantLetter = (name: string | undefined | null): string => {
  if (!name) return "";
  const trimmed = name.trim();
  return trimmed.length > 0 ? trimmed[0].toUpperCase() : "";
};
