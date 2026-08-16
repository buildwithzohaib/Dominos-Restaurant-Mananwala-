import { useMemo, useState } from "react";
import { X } from "lucide-react";

import { api } from "../services/api";
import { rupeesToPaisa, paisaToRupees } from "../utils/money";
import type { Product } from "../types";

export function AddStockModal({
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
  const [quantity, setQuantity] = useState<number | "">("");
  const [purchasePriceText, setPurchasePriceText] = useState(
    String(paisaToRupees(products[0]?.purchase_price ?? 0))
  );
  const [supplier, setSupplier] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const selected = useMemo(
    () => products.find((p) => p.id === productId) ?? null,
    [products, productId]
  );

  const addQty = Number(quantity) || 0;
  const newStock = (selected?.stock ?? 0) + addQty;
  const priceValid = purchasePriceText === "" || Number(purchasePriceText) >= 0;
  const canSave =
    selected != null &&
    addQty > 0 &&
    supplier.trim().length > 0 &&
    priceValid &&
    !busy;

  function selectProduct(id: number) {
    setProductId(id);
    // Prefill from the newly selected product's current acquisition cost — the
    // admin can still override it if this purchase's price is different.
    const product = products.find((p) => p.id === id);
    setPurchasePriceText(product ? String(paisaToRupees(product.purchase_price)) : "");
  }

  async function save() {
    // Re-checked here (not just via `disabled`) so a stray Enter-key submit can't
    // slip past the same guard the button uses.
    if (!selected || addQty <= 0 || !supplier.trim() || !priceValid || busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api.addStock(selected.id, {
        quantity: addQty,
        purchase_price: purchasePriceText === "" ? undefined : rupeesToPaisa(parseFloat(purchasePriceText) || 0),
        supplier: supplier.trim(),
      });
      onSaved(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add stock");
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
        <h2>Add Stock</h2>

        <div className="modal-field-grid">
          <label className="modal-field full">
            Item
            <select
              value={productId}
              onChange={(e) => selectProduct(Number(e.target.value))}
            >
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name_display} ({p.sku})
                </option>
              ))}
            </select>
          </label>

          <label className="modal-field">
            Quantity
            <input
              autoFocus
              type="number"
              min="1"
              value={quantity}
              onChange={(e) =>
                setQuantity(e.target.value === "" ? "" : Number(e.target.value))
              }
            />
          </label>

          <label className="modal-field">
            Purchase Price
            <input
              type="number"
              min="0"
              step="0.01"
              value={purchasePriceText}
              onChange={(e) => setPurchasePriceText(e.target.value)}
            />
          </label>

          <label className="modal-field full">
            Supplier
            <input
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              placeholder="e.g. ABC Traders"
            />
          </label>
        </div>

        <div className="stock-preview">
          <div>
            <span>Current Stock</span>
            <strong>{selected?.stock ?? 0}</strong>
          </div>
          <div className="arrow">→</div>
          <div>
            <span>New Stock</span>
            <strong>{newStock}</strong>
          </div>
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="modal-action-row">
          <button className="secondary-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="pay-button" disabled={!canSave} onClick={save}>
            {busy ? "Saving..." : "Add Stock"}
          </button>
        </div>
      </div>
    </div>
  );
}
