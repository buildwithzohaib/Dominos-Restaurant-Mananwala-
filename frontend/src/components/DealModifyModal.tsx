import { useState, useMemo } from "react";
import { X, Trash2 } from "lucide-react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import type { Product, DealModificationComponent, DealModifications } from "../types";

export function DealModifyModal({
  deal,
  onClose,
  onAccept,
}: {
  deal: Product;
  onClose: () => void;
  onAccept: (modifications: DealModifications) => void;
}) {
  const formatCurrency = useCurrencyFormat();
  const [components, setComponents] = useState<DealModificationComponent[]>(
    deal.components.map(c => ({
      product_id: c.product_id,
      quantity: c.quantity,
      size_id: c.size_id,
      was_removed: false,
    }))
  );
  const [priceOverride, setPriceOverride] = useState<string>("");
  const [error, setError] = useState("");

  // Calculate price changes, total, and validation
  const priceCalculation = useMemo(() => {
    const changes: { label: string; amount: number }[] = [];
    let total = deal.price;
    const active = components.filter(c => !c.was_removed);

    for (let i = 0; i < components.length; i++) {
      const comp = components[i];
      const original = deal.components[i];
      if (!original) continue;

      if (comp.was_removed) {
        // Removing: subtract full component price
        const removed = original.component_price;
        changes.push({
          label: `- Remove ${original.product_name}`,
          amount: -removed,
        });
        total -= removed;
      }
      // Size changes not yet implemented (Phase 11 Part 2 Step B)
    }

    return { changes, total, activeCount: active.length };
  }, [components, deal]);

  const finalPrice = priceOverride
    ? Math.floor(parseFloat(priceOverride) * 100 || 0)
    : priceCalculation.total;

  const handleRemove = (idx: number) => {
    setComponents(c => {
      const updated = [...c];
      updated[idx].was_removed = !updated[idx].was_removed;
      return updated;
    });
  };

  // Show error immediately if all components removed
  const validationError = priceCalculation.activeCount === 0
    ? "Deal cannot have all components removed."
    : "";

  const handleAccept = () => {
    if (validationError) {
      return;
    }
    onAccept({
      components,
      price: finalPrice,
      standard_price: deal.price,
    });
  };

  return (
    <div className="modal-backdrop">
      <div className="inventory-modal deal-modify-modal">
        <button className="modal-close" onClick={onClose}>
          <X />
        </button>

        <p className="eyebrow">MODIFY DEAL</p>
        <h2>{deal.name_display}</h2>

        {(error || validationError) && <div className="error-box deal-modify-error">{error || validationError}</div>}

        <div className="deal-modify-section">
          <h4 className="deal-modify-heading">Components</h4>
          <div className="deal-modify-components">
            {deal.components.map((comp, idx) => {
              const comp_mod = components[idx];
              const isRemoved = comp_mod.was_removed;
              return (
                <div
                  key={idx}
                  className={`deal-modify-component ${isRemoved ? "removed" : ""}`}
                >
                  <div className="deal-modify-component-info">
                    <strong>{comp.product_name}</strong>
                    {comp.size_name && <span className="component-size">({comp.size_name})</span>}
                  </div>
                  <button
                    className="row-action-button"
                    onClick={() => handleRemove(idx)}
                    title={isRemoved ? "Restore" : "Remove"}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        <div className="deal-modify-section">
          <h4 className="deal-modify-heading">Price</h4>
          <div className="deal-modify-breakdown">
            <div className="deal-modify-price-line">
              <span>Base price:</span>
              <strong>{formatCurrency(deal.price)}</strong>
            </div>
            {priceCalculation.changes.map((change, idx) => (
              <div key={idx} className={`deal-modify-price-line ${change.amount < 0 ? "negative" : ""}`}>
                <span>{change.label}:</span>
                <span>{formatCurrency(change.amount)}</span>
              </div>
            ))}
            {priceCalculation.changes.length > 0 && (
              <div className="deal-modify-price-line calculated">
                <span>Calculated:</span>
                <strong>{formatCurrency(priceCalculation.total)}</strong>
              </div>
            )}
          </div>

          <div className="deal-modify-price-input">
            <label className="deal-modify-label">Final Price</label>
            <input
              type="text"
              value={priceOverride || (finalPrice / 100).toFixed(2)}
              onChange={(e) => setPriceOverride(e.target.value)}
              placeholder={(finalPrice / 100).toFixed(2)}
              className="deal-modify-input"
            />
          </div>
        </div>

        <div className="deal-modify-actions">
          <button className="secondary-button" onClick={onClose}>
            Cancel
          </button>
          <button className="pay-button" onClick={handleAccept} disabled={!!validationError}>
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
