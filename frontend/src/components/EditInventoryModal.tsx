import { useState } from "react";
import { X } from "lucide-react";

import { api } from "../services/api";
import type { Product } from "../types";

export function EditInventoryModal({
  product,
  onClose,
  onSaved,
}: {
  product: Product;
  onClose: () => void;
  onSaved: (product: Product) => void;
}) {
  const [name, setName] = useState(product.name);
  const [sku, setSku] = useState(product.sku);
  const [minStock, setMinStock] = useState(String(product.min_stock));
  const [unit, setUnit] = useState(product.unit);
  const [purchasePrice, setPurchasePrice] = useState(String(product.purchase_price));
  const [price, setPrice] = useState(String(product.price));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function validate(): string | null {
    if (!name.trim()) return "Item name cannot be empty.";
    if (!sku.trim()) return "SKU cannot be empty.";
    if (!unit.trim()) return "Unit cannot be empty.";
    if (minStock === "" || Number(minStock) < 0) return "Minimum stock cannot be negative.";
    if (purchasePrice === "" || Number(purchasePrice) < 0) return "Purchase price cannot be negative.";
    if (price === "" || Number(price) < 0) return "Selling price cannot be negative.";
    return null;
  }

  async function save() {
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const updated = await api.updateInventoryItem(product.id, {
        name: name.trim(),
        sku: sku.trim(),
        min_stock: Number(minStock),
        unit: unit.trim(),
        purchase_price: Number(purchasePrice),
        price: Number(price),
      });
      onSaved(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save changes");
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
        <h2>Edit Item</h2>

        <div className="modal-field-grid">
          <label className="modal-field full">
            Item Name
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>

          <label className="modal-field">
            SKU
            <input value={sku} onChange={(e) => setSku(e.target.value)} />
          </label>

          <label className="modal-field">
            Unit
            <input value={unit} onChange={(e) => setUnit(e.target.value)} />
          </label>

          <label className="modal-field">
            Minimum Stock
            <input
              type="number"
              min="0"
              value={minStock}
              onChange={(e) => setMinStock(e.target.value)}
            />
          </label>

          <label className="modal-field">
            Current Stock
            <input value={product.stock} disabled title="Use Add Stock to change current stock" />
          </label>

          <label className="modal-field">
            Purchase Price
            <input
              type="number"
              min="0"
              step="0.01"
              value={purchasePrice}
              onChange={(e) => setPurchasePrice(e.target.value)}
            />
          </label>

          <label className="modal-field">
            Selling Price
            <input
              type="number"
              min="0"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
            />
          </label>
        </div>

        {error && <div className="error-box">{error}</div>}

        <button className="pay-button" disabled={busy} onClick={save}>
          {busy ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </div>
  );
}
