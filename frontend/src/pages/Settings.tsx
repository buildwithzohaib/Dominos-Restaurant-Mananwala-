import { useContext, useEffect, useState } from "react";
import { Save, AlertCircle, Trash2, RotateCcw, Plus } from "lucide-react";
import { SettingsContext } from "../context/SettingsContext";
import { useCatalog } from "../context/CatalogContext";
import { api, APIError } from "../services/api";
import type { SettingsUpdate } from "../types";

// Theme palette for swatches: accent color (large) + sidebar color (small)
const THEME_PALETTE = {
  amber: { accent: "#f3b32b", sidebar: "#111827", name: "Amber" },
  crimson: { accent: "#d6412f", sidebar: "#1a1113", name: "Crimson" },
  emerald: { accent: "#1ba774", sidebar: "#0f1c17", name: "Emerald" },
  ocean: { accent: "#2a78d6", sidebar: "#0f1b2d", name: "Ocean" },
  violet: { accent: "#7c5ce0", sidebar: "#171226", name: "Violet" },
  terracotta: { accent: "#d96a3a", sidebar: "#1d1512", name: "Terracotta" },
  "amber-dark": { accent: "#f5b301", sidebar: "#16181f", name: "Amber Dark" },
  "crimson-dark": { accent: "#e0533f", sidebar: "#1d1517", name: "Crimson Dark" },
  "emerald-dark": { accent: "#1bc287", sidebar: "#132019", name: "Emerald Dark" },
  "ocean-dark": { accent: "#3b8fe8", sidebar: "#141d2b", name: "Ocean Dark" },
  "violet-dark": { accent: "#8b6bf0", sidebar: "#1d1830", name: "Violet Dark" },
  "steel-dark": { accent: "#2bb3a3", sidebar: "#1a1e24", name: "Steel Dark" },
} as const;

type ThemeKey = keyof typeof THEME_PALETTE;

export function Settings() {
  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;
  const refreshSettings = settingsContext?.refreshSettings;

  const { tables, refresh: refreshCatalog } = useCatalog();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Tables state
  const [tables_local, setTablesLocal] = useState<typeof tables>([]);
  const [showRemoved, setShowRemoved] = useState(false);
  const [newTableName, setNewTableName] = useState("");
  const [editingTableId, setEditingTableId] = useState<number | null>(null);
  const [editingTableName, setEditingTableName] = useState("");
  const [tableLoading, setTableLoading] = useState(false);
  const [tableError, setTableError] = useState("");
  const [restoreTableId, setRestoreTableId] = useState<number | null>(null);

  // Backup & Restore state
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupError, setBackupError] = useState("");
  const [backupSuccess, setBackupSuccess] = useState("");

  // Hidden theme picker state (not persisted)
  const [versionClickCount, setVersionClickCount] = useState(0);
  const [selectedTheme, setSelectedTheme] = useState<ThemeKey>("amber");

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
      // Initialize selected theme from settings
      if (settings.theme && settings.theme in THEME_PALETTE) {
        setSelectedTheme(settings.theme as ThemeKey);
      }
    }
  }, [settings]);

  // Load all tables (active + removed) for the Settings UI, independent of CatalogContext
  useEffect(() => {
    async function loadAllTables() {
      try {
        const allTables = await api.getTables(true);  // includeInactive=true
        setTablesLocal(allTables);
      } catch (e) {
        // Silent fail; show what we have
      }
    }
    loadAllTables();
  }, []);

  // Refresh both: the Settings table list (all tables) and POS catalog (active only)
  async function refreshTablesList() {
    try {
      const allTables = await api.getTables(true);  // Settings UI needs all tables
      setTablesLocal(allTables);
    } catch (e) {
      // Silent fail; show what we have
    }
    try {
      await refreshCatalog();  // POS dropdown needs active only
    } catch (e) {
      // Silent fail
    }
  }

  // Table handlers
  async function handleAddTable() {
    if (!newTableName.trim()) {
      setTableError("Table name is required");
      return;
    }

    setTableLoading(true);
    setTableError("");
    setRestoreTableId(null);

    try {
      await api.createTable(newTableName);
      setNewTableName("");
      await refreshTablesList();
    } catch (e) {
      if (e instanceof APIError && e.detail?.inactive_table_id) {
        // Special case: name belongs to an inactive table
        setRestoreTableId(e.detail.inactive_table_id);
        setTableError(e.message);
      } else {
        const msg = e instanceof Error ? e.message : "Failed to add table";
        setTableError(msg);
      }
    } finally {
      setTableLoading(false);
    }
  }

  async function handleRestoreTable(tableId: number) {
    setTableLoading(true);
    setTableError("");
    setRestoreTableId(null);

    try {
      await api.activateTable(tableId);
      setNewTableName("");
      await refreshTablesList();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to restore table";
      setTableError(msg);
    } finally {
      setTableLoading(false);
    }
  }

  async function handleRenameTable(tableId: number) {
    if (!editingTableName.trim()) {
      setTableError("Table name is required");
      return;
    }

    setTableLoading(true);
    setTableError("");

    try {
      await api.renameTable(tableId, editingTableName);
      setEditingTableId(null);
      setEditingTableName("");
      await refreshTablesList();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to rename table";
      setTableError(msg);
    } finally {
      setTableLoading(false);
    }
  }

  async function handleRemoveTable(tableId: number) {
    setTableLoading(true);
    setTableError("");

    try {
      await api.deactivateTable(tableId);
      await refreshTablesList();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to remove table";
      setTableError(msg);
    } finally {
      setTableLoading(false);
    }
  }

  async function handleRestoreBackup() {
    // Confirm first: warn about destructive action
    const confirmed = window.confirm(
      "Restore from backup? This will overwrite the current database with the most recent backup. All data since the backup was taken will be lost. The server must be restarted afterward."
    );

    if (!confirmed) return;

    setBackupLoading(true);
    setBackupError("");
    setBackupSuccess("");

    try {
      const response = await api.restoreBackup();

      if (response.success) {
        const msg = `${response.message}`;
        setBackupSuccess(msg);
        // Don't clear success message auto, since it contains important restart info
      } else {
        setBackupError(response.error || "Restore failed");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Restore failed";
      setBackupError(msg);
    } finally {
      setBackupLoading(false);
    }
  }

  function handleVersionLabelClick() {
    setVersionClickCount((prev) => prev + 1);
  }

  async function handleThemeSwitchClick(theme: ThemeKey) {
    setSelectedTheme(theme);
    // Apply theme immediately to DOM
    document.documentElement.dataset.theme = theme;
    // Save to settings
    try {
      await api.updateSettings({ theme });
    } catch (e) {
      // Silent fail: theme is already applied visually
      console.error("Failed to save theme:", e);
    }
  }

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

        {/* Table Management */}
        <fieldset>
          <legend>Table Management <span className="tables-legend-subtitle">(changes take effect immediately)</span></legend>

          {tableError && (
            <div className="error-box">
              <div>{tableError}</div>
              {restoreTableId !== null && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => handleRestoreTable(restoreTableId)}
                  disabled={tableLoading}
                >
                  {tableLoading ? "Restoring..." : "Restore this table"}
                </button>
              )}
            </div>
          )}

          {/* Add Table Row */}
          <div className="tables-add-row">
            <label>
              Add Table
              <input
                type="text"
                value={newTableName}
                onChange={(e) => setNewTableName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddTable();
                  }
                }}
                placeholder="Table name"
                disabled={tableLoading}
              />
            </label>
            <button
              type="button"
              className="pay-button"
              onClick={handleAddTable}
              disabled={tableLoading || !newTableName.trim()}
            >
              <Plus size={16} />
              Add
            </button>
          </div>

          {/* Show Removed Toggle */}
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={showRemoved}
              onChange={(e) => setShowRemoved(e.target.checked)}
              disabled={tableLoading}
            />
            Show removed tables
          </label>

          {/* Tables List */}
          {tables_local.length === 0 ? (
            <p className="tables-empty">No tables yet. Add one above.</p>
          ) : (
            <div className="tables-list">
              {tables_local.map((table) => {
                const isRemoved = !table.active;
                const isVisible = isRemoved ? showRemoved : true;

                if (!isVisible) return null;

                return (
                  <div
                    key={table.id}
                    className={`table-item ${isRemoved ? "removed" : ""}`}
                  >
                    {editingTableId === table.id ? (
                      <>
                        <input
                          type="text"
                          value={editingTableName}
                          onChange={(e) => setEditingTableName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              handleRenameTable(table.id);
                            } else if (e.key === "Escape") {
                              setEditingTableId(null);
                              setEditingTableName("");
                            }
                          }}
                          autoFocus
                          className="table-item-edit-input"
                          disabled={tableLoading}
                        />
                        <button
                          type="button"
                          className="pay-button table-item-button-small"
                          onClick={() => handleRenameTable(table.id)}
                          disabled={tableLoading}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          className="secondary-button table-item-button-small"
                          onClick={() => {
                            setEditingTableId(null);
                            setEditingTableName("");
                          }}
                          disabled={tableLoading}
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <span className="table-item-name">
                          {table.name}
                          {isRemoved && <span className="table-item-removed-label">(removed)</span>}
                        </span>
                        {!isRemoved && (
                          <button
                            type="button"
                            className="row-action-button"
                            onClick={() => {
                              setEditingTableId(table.id);
                              setEditingTableName(table.name);
                            }}
                            disabled={tableLoading}
                            title="Rename"
                          >
                            Edit
                          </button>
                        )}
                        {isRemoved ? (
                          <button
                            type="button"
                            className="row-action-button"
                            onClick={() => handleRestoreTable(table.id)}
                            disabled={tableLoading}
                            title="Restore"
                          >
                            <RotateCcw size={16} />
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="row-action-button"
                            onClick={() => handleRemoveTable(table.id)}
                            disabled={tableLoading}
                            title="Remove"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Active Count */}
          <div className="tables-count">
            {tables_local.filter((t) => t.active).length} active table{tables_local.filter((t) => t.active).length !== 1 ? "s" : ""}
          </div>
        </fieldset>

        {/* Backup & Restore */}
        <fieldset>
          <legend>Backup & Restore</legend>

          <p className="fieldset-description">
            Backups are created automatically once per day. You can restore from the most recent backup here, but this will overwrite the current database.
          </p>

          {backupError && (
            <div className="error-box">
              {backupError}
            </div>
          )}

          {backupSuccess && (
            <div className="success-box">
              {backupSuccess}
            </div>
          )}

          <button
            type="button"
            className="secondary-button"
            onClick={handleRestoreBackup}
            disabled={backupLoading}
          >
            {backupLoading ? "Restoring..." : "Restore from Backup"}
          </button>
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

      {/* Version Label (footer, hidden clickable) */}
      <div className="settings-footer">
        <button
          onClick={handleVersionLabelClick}
          className="version-label"
          title="v1.0"
          aria-label="Version"
        >
          v1.0
        </button>

        {/* Hidden Appearance Section (unlocked after 7 clicks) */}
        {versionClickCount >= 7 && (
          <fieldset className="appearance-fieldset">
            <legend>Appearance</legend>
            <div className="theme-swatches">
              {(Object.keys(THEME_PALETTE) as ThemeKey[]).map((themeKey) => {
                const themeInfo = THEME_PALETTE[themeKey];
                const isSelected = selectedTheme === themeKey;
                return (
                  <button
                    key={themeKey}
                    type="button"
                    className={`theme-swatch ${isSelected ? "selected" : ""}`}
                    onClick={() => handleThemeSwitchClick(themeKey)}
                    title={themeInfo.name}
                    aria-label={`Select ${themeInfo.name} theme`}
                  >
                    <div className="theme-swatch-colors">
                      <div
                        className="theme-swatch-accent"
                        style={{ backgroundColor: themeInfo.accent }}
                      ></div>
                      <div
                        className="theme-swatch-sidebar"
                        style={{ backgroundColor: themeInfo.sidebar }}
                      ></div>
                    </div>
                    <div className="theme-swatch-label">{themeInfo.name}</div>
                  </button>
                );
              })}
            </div>
          </fieldset>
        )}
      </div>
    </div>
  );
}
