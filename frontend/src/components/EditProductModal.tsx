import { useState } from "react";
import { X } from "lucide-react";
import { api } from "../services/api";
import { rupeesToPaisa, paisaToRupees } from "../utils/money";
import type { Category, Product, ProductUpdateInput } from "../types";

export function EditProductModal({
  product,
  categories,
  onClose,
  onSaved,
}: {
  product: Product;
  categories: Category[];
  onClose: () => void;
  onSaved: (product: Product) => void;
}) {
  const [formData, setFormData] = useState<ProductUpdateInput>({
    name: product.name_display,
    category_id: product.category_id,
    price: Number(product.price),
    purchase_price: Number(product.purchase_price),
    min_stock: product.min_stock,
    unit: product.unit,
  });

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [priceText, setPriceText] = useState(
    formData.price !== undefined ? String(paisaToRupees(formData.price)) : ""
  );
  const [purchasePriceText, setPurchasePriceText] = useState(
    formData.purchase_price !== undefined ? String(paisaToRupees(formData.purchase_price)) : ""
  );

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const updated = await api.updateProduct(product.id, {
        ...formData,
        price: priceText !== "" ? rupeesToPaisa(parseFloat(priceText) || 0) : undefined,
        purchase_price: purchasePriceText !== "" ? rupeesToPaisa(parseFloat(purchasePriceText) || 0) : undefined,
      });
      onSaved(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update product");
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

        <p className="eyebrow">PRODUCTS</p>
        <h2>Edit Product</h2>

        <div className="modal-field-grid">
          <label className="modal-field">
            Category
            <select
              value={formData.category_id || product.category_id}
              onChange={(e) =>
                setFormData({ ...formData, category_id: Number(e.target.value) })
              }
            >
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name_display}
                  {!cat.active ? " (inactive)" : ""}
                </option>
              ))}
              {/* Show product's current category even if not in the list (e.g., inactive) */}
              {product.category && !categories.find(c => c.id === product.category.id) && (
                <option value={product.category.id} selected>
                  {product.category.name_display} (inactive)
                </option>
              )}
            </select>
          </label>

          <label className="modal-field">
            Product Name
            <input
              value={formData.name || ""}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
            />
          </label>

          <label className="modal-field">
            SKU (immutable)
            <div style={{ padding: "8px 0", fontFamily: "monospace", fontSize: "13px", color: "#374151" }}>
              {product.sku}
            </div>
          </label>

          <label className="modal-field">
            Selling Price
            <input
              type="number"
              step="0.01"
              value={priceText}
              onChange={(e) => setPriceText(e.target.value)}
            />
          </label>

          <label className="modal-field">
            Purchase Price
            <input
              type="number"
              step="0.01"
              value={purchasePriceText}
              onChange={(e) => setPurchasePriceText(e.target.value)}
            />
          </label>

          <label className="modal-field">
            Minimum Stock
            <input
              type="number"
              value={formData.min_stock !== undefined ? formData.min_stock : ""}
              onChange={(e) =>
                setFormData({ ...formData, min_stock: Number(e.target.value) })
              }
            />
          </label>

          <label className="modal-field">
            Unit
            <input
              value={formData.unit || ""}
              onChange={(e) =>
                setFormData({ ...formData, unit: e.target.value })
              }
            />
          </label>
        </div>

        <p className="muted" style={{ fontSize: "12px", marginTop: "12px" }}>
          Note: Use Inventory page to modify stock quantity. Stock changes here create audit trail.
        </p>

        {error && <div className="error-box">{error}</div>}

        <div className="modal-action-row">
          <button className="secondary-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="pay-button" disabled={busy} onClick={submit}>
            {busy ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
