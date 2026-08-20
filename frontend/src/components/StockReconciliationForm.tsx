import { useState } from "react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { api } from "../services/api";
import type { Product, StockReconciliationIn } from "../types";

export function StockReconciliationForm({
  products,
  onClose,
  onSaved,
}: {
  products: Product[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const formatCurrency = useCurrencyFormat();
  const [countedValues, setCountedValues] = useState<{ [productId: number]: string }>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");

  function handleCountChange(productId: number, value: string) {
    setCountedValues((prev) => ({
      ...prev,
      [productId]: value,
    }));
  }

  async function handleSubmit() {
    // Build payload from only rows where user typed something
    const items = Object.entries(countedValues)
      .filter(([_, value]) => value.trim() !== "")
      .map(([productId, value]) => ({
        product_id: parseInt(productId),
        counted_quantity: parseInt(value) || 0,
      }));

    if (items.length === 0) {
      setError("Please enter a counted quantity for at least one product.");
      return;
    }

    setBusy(true);
    setError("");
    setResult("");

    try {
      const payload: StockReconciliationIn = { items };
      const movements = await api.reconcileStock(payload);

      // Success: show result and trigger refresh
      setResult(`${movements.length} product${movements.length === 1 ? "" : "s"} adjusted.`);
      setCountedValues({});

      // Refresh and close after a short delay so user sees the success message
      setTimeout(() => {
        onSaved();
      }, 500);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not save reconciliation. No changes were made."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="inventory-card">
      <div className="page-header" style={{ marginBottom: "16px", paddingLeft: "16px" }}>
        <p className="eyebrow">INVENTORY</p>
        <h2>Stock Count Reconciliation</h2>
        <p className="reconciliation-instructions">
          Enter the quantity you counted for each product. Leave blank to skip.
        </p>
      </div>

      {error && <div className="error-box" style={{ margin: "0 16px 16px" }}>{error}</div>}
      {result && <div className="success-box" style={{ margin: "0 16px 16px" }}>{result}</div>}

      <div style={{ overflowX: "auto" }}>
        <div className="reconciliation-head">
          <span>Product</span>
          <span>SKU</span>
          <span>Current Stock</span>
          <span>Counted Quantity</span>
        </div>

        {products.map((product) => (
          <div className="reconciliation-row" key={product.id}>
            <span>
              <strong>{product.name_display}</strong>
            </span>
            <span>{product.sku}</span>
            <span>{product.stock}</span>
            <span>
              <input
                type="number"
                min="0"
                placeholder="—"
                value={countedValues[product.id] ?? ""}
                onChange={(e) => handleCountChange(product.id, e.target.value)}
                disabled={busy}
              />
            </span>
          </div>
        ))}
      </div>

      <div className="reconciliation-actions">
        <button className="secondary-button" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button
          className="pay-button"
          onClick={handleSubmit}
          disabled={busy || Object.values(countedValues).every((v) => v.trim() === "")}
        >
          {busy ? "Reconciling..." : "Reconcile Stock"}
        </button>
      </div>
    </div>
  );
}
