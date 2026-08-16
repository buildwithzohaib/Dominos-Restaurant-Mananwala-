import { useContext } from "react";
import { SettingsContext } from "../context/SettingsContext";
import { formatMoney } from "../utils/money";

/**
 * Hook that returns a currency formatter function using the settings currency symbol.
 * Falls back to default (Rs.) if settings haven't loaded yet.
 */
export function useCurrencyFormat() {
  const context = useContext(SettingsContext);

  if (!context) {
    throw new Error("useCurrencyFormat must be used within SettingsProvider");
  }

  const { settings } = context;
  const currencySymbol = settings?.currency_symbol || "Rs. ";

  return (paisa: number | null | undefined) =>
    formatMoney(paisa, currencySymbol);
}
