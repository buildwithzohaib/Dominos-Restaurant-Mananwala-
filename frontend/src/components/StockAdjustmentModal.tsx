import { useMemo, useState } from "react";
import { X } from "lucide-react";

import { api } from "../services/api";
import type { AdjustmentReason, Product } from "../types";

const REASONS: { value: AdjustmentReason; label: string }[] = [
  { value: "DAMAGED", label: "Damaged" },
  { value: "EXPIRED", label: "Expired" },
  { value: "LOST", label: "Lost" },
  { value: "MANUAL_CORRECTION", label: "Manual Correction" },
  { value: "OTHER", label: "Other" },
];

export function StockAdjustmentModal({
  products,
  onClose,
  onSaved,
}: {
  products: Product[];
  onClose: () => void;
  onSaved: (product: Product) => void;
}) {
  const [productId, setProductId] = useState<number | "">(
    products[0]?.id ?? ""
  );
  const [adjustment, setAdjustment] = useState<string>("");
  const [reason, setReason] = useState<AdjustmentReason>("DAMAGED");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const selected = useMemo(
    () => products.find((p) => p.id === productId) ?? null,
    [products, productId]
  );

  // Accept a signed integer typed directly ("-2", "+5"); blank/"-"/"+" mid-typing
  // parses to 0 rather than NaN so the preview doesn't flicker.
  const change = adjustment === "" || adjustment === "-" || adjustment === "+"
    ? 0
    : Number(adjustment) || 0;
  const newStock = (selected?.stock ?? 0) + change;
  const canSave =
    selected != null &&
    change !== 0 &&
    newStock >= 0 &&
    !busy;

  async function save() {
    if (!selected || change === 0 || newStock < 0 || busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api.adjustStock(selected.id, {
        quantity_change: change,
        reason,
        note: reason === "OTHER" ? note.trim() || undefined : undefined,
      });
      onSaved(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the adjustment");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="inventory-modal">
        <button className="modal-close" onClick={onClose}>
          <X />
        </button>

        <p className="eyebrow">INVENTORY</p>
        <h2>Stock Adjustment</h2>

        <div className="modal-field-grid">
          <label className="modal-field full">
            Item
            <select
              value={productId}
              onChange={(e) => setProductId(Number(e.target.value))}
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name_display} ({p.sku})
                </option>
              ))}
            </select>
          </label>

          <label className="modal-field">
            Adjustment
            <input
              autoFocus
              type="number"
              step="1"
              placeholder="e.g. -2 or 5"
              value={adjustment}
              onChange={(e) => setAdjustment(e.target.value)}
            />
          </label>

          <label className="modal-field">
            Reason
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value as AdjustmentReason)}
            >
              {REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>

          {reason === "OTHER" && (
            <label className="modal-field full">
              Explanation
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Short explanation"
              />
            </label>
          )}
        </div>

        <div className="stock-preview">
          <div>
            <span>Current Stock</span>
            <strong>{selected?.stock ?? 0}</strong>
          </div>
          <div className="arrow">→</div>
          <div>
            <span>New Stock</span>
            <strong className={newStock < 0 ? "stock-preview-negative" : ""}>
              {newStock}
            </strong>
          </div>
        </div>

        {newStock < 0 && (
          <div className="error-box">
            Insufficient stock for this adjustment.
          </div>
        )}

        {error && <div className="error-box">{error}</div>}

        <div className="modal-action-row">
          <button className="secondary-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="pay-button" disabled={!canSave} onClick={save}>
            {busy ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
