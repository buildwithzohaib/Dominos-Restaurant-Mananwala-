import { useContext, useEffect, useState } from "react";
import { Save, AlertCircle } from "lucide-react";
import { SettingsContext } from "../context/SettingsContext";
import { api } from "../services/api";
import type { SettingsUpdate } from "../types";

export function Settings() {
  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;
  const refreshSettings = settingsContext?.refreshSettings;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Form state
  const [restaurantName, setRestaurantName] = useState("");
  const [restaurantAddress, setRestaurantAddress] = useState("");
  const [restaurantPhone, setRestaurantPhone] = useState("");
  const [currencySymbol, setCurrencySymbol] = useState("");
  const [taxRateText, setTaxRateText] = useState(""); // Text state: % display
  const [taxEnabled, setTaxEnabled] = useState(false);
  const [deliveryChargeText, setDeliveryChargeText] = useState(""); // Text state: Rupees display
  const [dayStartsAt, setDayStartsAt] = useState("");
  const [receiptFooterText, setReceiptFooterText] = useState("");

  // Initialize form from settings on load
  useEffect(() => {
    if (settings) {
      setRestaurantName(settings.restaurant_name || "");
      setRestaurantAddress(settings.restaurant_address || "");
      setRestaurantPhone(settings.restaurant_phone || "");
      setCurrencySymbol(settings.currency_symbol || "");
      setTaxRateText(String((settings.tax_rate || 0) / 100)); // Convert bp to %
      setTaxEnabled(settings.tax_enabled || false);
      setDeliveryChargeText(String((settings.delivery_charge || 0) / 100)); // Convert paisa to Rupees
      setDayStartsAt(settings.day_starts_at || "06:00");
      setReceiptFooterText(settings.receipt_footer_text || "");
    }
  }, [settings]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");

    // Client-side validation: only check obviously empty required fields
    if (!restaurantName.trim()) {
      setError("Restaurant name is required");
      return;
    }
    if (!currencySymbol.trim()) {
      setError("Currency symbol is required");
      return;
    }

    setLoading(true);

    try {
      // Convert tax_rate from % string to basis points (integer)
      const taxRateBp = Math.round(parseFloat(taxRateText) * 100);
      // Convert delivery_charge from Rupees string to paisa (integer)
      const deliveryChargePaisa = Math.round(parseFloat(deliveryChargeText) * 100);

      const payload: SettingsUpdate = {
        restaurant_name: restaurantName.trim(),
        restaurant_address: restaurantAddress.trim(),
        restaurant_phone: restaurantPhone.trim(),
        currency_symbol: currencySymbol.trim(),
        tax_rate: taxRateBp,
        tax_enabled: taxEnabled,
        delivery_charge: deliveryChargePaisa,
        day_starts_at: dayStartsAt,
        receipt_footer_text: receiptFooterText.trim(),
      };

      await api.updateSettings(payload);
      setSuccess("Settings saved successfully");

      // Refresh settings context so all components update
      if (refreshSettings) {
        await refreshSettings();
      }

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(""), 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to save settings";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <div>
          <p className="eyebrow">CONFIGURATION</p>
          <h1>Settings</h1>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {success && (
        <div className="success-banner">
          ✓ {success}
        </div>
      )}

      <form onSubmit={handleSave} className="settings-form">
        {/* Restaurant Information */}
        <fieldset>
          <legend>Restaurant Information</legend>

          <label>
            Restaurant Name
            <input
              type="text"
              value={restaurantName}
              onChange={(e) => setRestaurantName(e.target.value)}
              placeholder="Enter restaurant name"
            />
          </label>

          <label>
            Address
            <textarea
              value={restaurantAddress}
              onChange={(e) => setRestaurantAddress(e.target.value)}
              placeholder="Enter restaurant address"
              rows={3}
              maxLength={100}
            />
            <span className="char-count">{restaurantAddress.length} / 100</span>
          </label>

          <label>
            Phone
            <input
              type="tel"
              value={restaurantPhone}
              onChange={(e) => setRestaurantPhone(e.target.value)}
              placeholder="Enter phone number"
            />
          </label>
        </fieldset>

        {/* Financial Settings */}
        <fieldset>
          <legend>Financial Settings</legend>

          <label>
            Currency Symbol
            <input
              type="text"
              value={currencySymbol}
              onChange={(e) => setCurrencySymbol(e.target.value)}
              placeholder="e.g., Rs. , $, €"
              maxLength={10}
            />
          </label>

          <label>
            <span>Enable Tax</span>
            <input
              type="checkbox"
              checked={taxEnabled}
              onChange={(e) => setTaxEnabled(e.target.checked)}
            />
          </label>

          {taxEnabled && (
            <label>
              Tax Rate (%)
              <input
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={taxRateText}
                onChange={(e) => setTaxRateText(e.target.value)}
                placeholder="e.g., 16 for 16%"
              />
            </label>
          )}

          <label>
            Default Delivery Charge
            <input
              type="number"
              min="0"
              step="0.01"
              value={deliveryChargeText}
              onChange={(e) => setDeliveryChargeText(e.target.value)}
              placeholder="e.g., 200 for Rs. 200"
            />
          </label>
        </fieldset>

        {/* Operations Settings */}
        <fieldset>
          <legend>Operations Settings</legend>

          <label>
            Business Day Starts At
            <input
              type="time"
              value={dayStartsAt}
              onChange={(e) => setDayStartsAt(e.target.value)}
            />
          </label>
        </fieldset>

        {/* Receipt Customization */}
        <fieldset>
          <legend>Receipt Customization</legend>

          <label>
            Receipt Footer Text
            <textarea
              value={receiptFooterText}
              onChange={(e) => setReceiptFooterText(e.target.value)}
              placeholder="e.g., Thank you for your visit!"
              rows={3}
              maxLength={80}
            />
            <span className="char-count">{receiptFooterText.length} / 80</span>
          </label>
        </fieldset>

        {/* Save Button */}
        <div className="settings-actions">
          <button
            type="submit"
            className="pay-button"
            disabled={loading}
          >
            <Save size={18} />
            {loading ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
