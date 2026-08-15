import { useState } from "react";
import { X } from "lucide-react";
import { api } from "../services/api";
import { rupeesToPaisa, paisaToRupees } from "../utils/money";
import type { Category, Product, ProductCreateInput } from "../types";

export function AddProductModal({
  categories,
  onClose,
  onSaved,
}: {
  categories: Category[];
  onClose: () => void;
  onSaved: (product: Product) => void;
}) {
  const [formData, setFormData] = useState<ProductCreateInput>({
    category_id: categories[0]?.id || 1,
    name: "",
    price: 100,
    purchase_price: 50,
    stock: 0,
    min_stock: 5,
    sku: "",
    unit: "Piece",
  });

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [priceText, setPriceText] = useState(String(paisaToRupees(formData.price)));
  const [purchasePriceText, setPurchasePriceText] = useState(
    formData.purchase_price ? String(paisaToRupees(formData.purchase_price)) : ""
  );

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const product = await api.createProduct({
        ...formData,
        price: rupeesToPaisa(parseFloat(priceText) || 0),
        purchase_price: purchasePriceText ? rupeesToPaisa(parseFloat(purchasePriceText) || 0) : undefined,
      });
      onSaved(product);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create product");
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
        <h2>Add Product</h2>

        <div className="modal-field-grid">
          <label className="modal-field">
            Category ID
            <input
              type="number"
              value={formData.category_id}
              onChange={(e) =>
                setFormData({ ...formData, category_id: Number(e.target.value) })
              }
            />
          </label>

          <label className="modal-field">
            Product Name
            <input
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              placeholder="Product name"
            />
          </label>

          <label className="modal-field">
            SKU
            <input
              value={formData.sku || ""}
              onChange={(e) =>
                setFormData({ ...formData, sku: e.target.value })
              }
              placeholder="Auto-generated if empty"
            />
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
            Initial Stock
            <input
              type="number"
              value={formData.stock || 0}
              onChange={(e) =>
                setFormData({ ...formData, stock: Number(e.target.value) })
              }
            />
          </label>

          <label className="modal-field">
            Minimum Stock
            <input
              type="number"
              value={formData.min_stock}
              onChange={(e) =>
                setFormData({ ...formData, min_stock: Number(e.target.value) })
              }
            />
          </label>

          <label className="modal-field">
            Unit
            <input
              value={formData.unit}
              onChange={(e) =>
                setFormData({ ...formData, unit: e.target.value })
              }
              placeholder="Piece, Bottle, Portion, etc."
            />
          </label>
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="modal-action-row">
          <button className="secondary-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="pay-button" disabled={busy || !formData.name} onClick={submit}>
            {busy ? "Creating..." : "Create Product"}
          </button>
        </div>
      </div>
    </div>
  );
}
