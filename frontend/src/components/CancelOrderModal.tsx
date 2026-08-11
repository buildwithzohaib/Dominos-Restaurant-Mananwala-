import { useState } from "react";
import { X } from "lucide-react";

import { api } from "../services/api";
import type { CancellationReason, Order } from "../types";

const REASONS: { value: CancellationReason; label: string }[] = [
  { value: "CUSTOMER_CHANGED_ORDER", label: "Customer changed order" },
  { value: "WRONG_ORDER", label: "Wrong order" },
  { value: "PAYMENT_ISSUE", label: "Payment issue" },
  { value: "DUPLICATE_ORDER", label: "Duplicate order" },
  { value: "OTHER", label: "Other" },
];

export function CancelOrderModal({
  order,
  onClose,
  onCancelled,
}: {
  order: Order;
  onClose: () => void;
  onCancelled: (order: Order) => void;
}) {
  const [reason, setReason] = useState<CancellationReason>("CUSTOMER_CHANGED_ORDER");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const noteRequired = reason === "OTHER";
  const canConfirm = !busy && (!noteRequired || note.trim().length > 0);

  async function confirm() {
    if (!canConfirm) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api.cancelOrder(order.id, {
        reason,
        note: noteRequired ? note.trim() : undefined,
      });
      onCancelled(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not cancel the order");
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

        <p className="eyebrow">ORDERS</p>
        <h2>Cancel Order?</h2>

        <p className="muted" style={{ marginTop: 4 }}>
          Are you sure you want to cancel Order {order.order_number}? This cannot be undone.
        </p>

        <div className="modal-field-grid">
          <label className="modal-field full">
            Reason
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value as CancellationReason)}
            >
              {REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>

          {noteRequired && (
            <label className="modal-field full">
              Please specify
              <input
                autoFocus
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Short explanation"
              />
            </label>
          )}
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="modal-action-row">
          <button className="secondary-button" onClick={onClose} disabled={busy}>
            Keep Order
          </button>
          <button className="pay-button danger" disabled={!canConfirm} onClick={confirm}>
            {busy ? "Cancelling..." : "Cancel Order"}
          </button>
        </div>
      </div>
    </div>
  );
}
