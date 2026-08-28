import { useState, useMemo } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { api } from "../services/api";
import { rupeesToPaisa, paisaToRupees } from "../utils/money";
import { useCatalog } from "../context/CatalogContext";
import type { Category, DealOut, DealCreate, DealUpdate, DealComponentCreate, Product } from "../types";

interface DealComponentForm {
  product_id: number;
  quantity: number;
  size_id: number | null;
}

interface DealFormState {
  category_id: number | null;
  name: string;
  price: number;
  components: DealComponentForm[];
}

export function DealForm({
  deal,
  categories,
  onClose,
  onSaved,
}: {
  deal?: DealOut;
  categories: Category[];
  onClose: () => void;
  onSaved: (deal: DealOut) => void;
}) {
  const { allProducts, allCategories } = useCatalog();

  // Filter out deals from the product list (only show regular products)
  const availableProducts = useMemo(
    () => allProducts.filter((p) => p.stock_status !== undefined), // Regular products have stock_status
    [allProducts]
  );

  const [formData, setFormData] = useState<DealFormState>(
    deal
      ? {
          category_id: deal.category_id,
          name: deal.name_display,
          price: deal.price,
          components: deal.components.map((c) => ({
            product_id: c.product_id,
            quantity: c.quantity,
            size_id: c.size_id,
          })),
        }
      : {
          category_id: null,
          name: "",
          price: 25000,
          components: [],
        }
  );

  const [priceText, setPriceText] = useState(String(paisaToRupees(formData.price)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function addComponent() {
    setFormData({
      ...formData,
      components: [...formData.components, { product_id: 0, quantity: 1, size_id: null }],
    });
  }

  function removeComponent(index: number) {
    setFormData({
      ...formData,
      components: formData.components.filter((_, i) => i !== index),
    });
  }

  function updateComponent(index: number, updates: Partial<DealComponentForm>) {
    const updated = [...formData.components];
    updated[index] = { ...updated[index], ...updates };
    setFormData({ ...formData, components: updated });
  }

  function getProductName(productId: number): string {
    return availableProducts.find((p) => p.id === productId)?.name_display || "Unknown";
  }

  function getProductSizes(productId: number) {
    return availableProducts.find((p) => p.id === productId)?.sizes || [];
  }

  async function submit() {
    // Validation
    if (formData.category_id === null) {
      setError("Please select a category");
      return;
    }

    if (!formData.name.trim()) {
      setError("Deal name cannot be empty");
      return;
    }

    if (formData.components.length === 0) {
      setError("Add at least one component");
      return;
    }

    for (let i = 0; i < formData.components.length; i++) {
      const comp = formData.components[i];
      if (comp.product_id === 0) {
        setError(`Component ${i + 1}: Select a product`);
        return;
      }
      if (comp.quantity < 1) {
        setError(`Component ${i + 1}: Quantity must be at least 1`);
        return;
      }
      if (comp.size_id !== null) {
        const sizes = getProductSizes(comp.product_id);
        if (!sizes.find((s) => s.id === comp.size_id)) {
          setError(`Component ${i + 1}: Invalid size selection`);
          return;
        }
      }
    }

    setBusy(true);
    setError("");
    try {
      const price = rupeesToPaisa(parseFloat(priceText) || 0);
      if (price <= 0) {
        setError("Deal price must be positive");
        setBusy(false);
        return;
      }

      const components: DealComponentCreate[] = formData.components.map((c) => ({
        product_id: c.product_id,
        quantity: c.quantity,
        size_id: c.size_id,
      }));

      let result: DealOut;
      if (deal) {
        result = await api.updateDeal(deal.id, {
          category_id: formData.category_id,
          name: formData.name.trim(),
          price,
          components,
        });
      } else {
        result = await api.createDeal({
          category_id: formData.category_id,
          name: formData.name.trim(),
          price,
          components,
        });
      }

      onSaved(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save deal");
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

        <p className="eyebrow">DEALS</p>
        <h2>{deal ? "Edit Deal" : "Add Deal"}</h2>

        <div className="modal-field-grid">
          <label className="modal-field">
            Category
            <select
              value={formData.category_id ?? ""}
              onChange={(e) =>
                setFormData({ ...formData, category_id: e.target.value ? Number(e.target.value) : null })
              }
            >
              <option value="">Select a category</option>
              {allCategories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name_display}
                  {!cat.active ? " (inactive)" : ""}
                </option>
              ))}
            </select>
          </label>

          <label className="modal-field">
            Deal Name
            <input
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="E.g., Pizza + Drink Combo"
            />
          </label>

          <label className="modal-field">
            Deal Price (Rs.)
            <input
              type="number"
              step="0.01"
              value={priceText}
              onChange={(e) => setPriceText(e.target.value)}
            />
          </label>
        </div>

        <div className="modal-section">
          <div className="modal-section-header">
            <h3>Components</h3>
            <button className="secondary-button" onClick={addComponent} disabled={busy}>
              <Plus size={14} /> Add Component
            </button>
          </div>

          {formData.components.length === 0 ? (
            <div className="modal-empty">No components added yet</div>
          ) : (
            <div className="deal-components-list">
              {formData.components.map((comp, idx) => {
                const product = availableProducts.find((p) => p.id === comp.product_id);
                const sizes = product?.sizes || [];

                return (
                  <div key={idx} className="deal-component-row">
                    <select
                      value={comp.product_id}
                      onChange={(e) =>
                        updateComponent(idx, {
                          product_id: Number(e.target.value),
                          size_id: null, // Reset size when product changes
                        })
                      }
                      className="component-product-select"
                    >
                      <option value={0}>Select product...</option>
                      {availableProducts.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name_display}
                        </option>
                      ))}
                    </select>

                    <input
                      type="number"
                      min="1"
                      value={comp.quantity}
                      onChange={(e) =>
                        updateComponent(idx, { quantity: Math.max(1, Number(e.target.value)) })
                      }
                      className="component-quantity-input"
                      placeholder="Qty"
                    />

                    {sizes.length > 0 ? (
                      <select
                        value={comp.size_id ?? ""}
                        onChange={(e) =>
                          updateComponent(idx, {
                            size_id: e.target.value ? Number(e.target.value) : null,
                          })
                        }
                        className="component-size-select"
                      >
                        <option value="">No size</option>
                        {sizes.map((size) => (
                          <option key={size.id} value={size.id}>
                            {size.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="component-size-placeholder">No sizes</div>
                    )}

                    <button
                      className="row-action-button"
                      onClick={() => removeComponent(idx)}
                      title="Remove component"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="modal-actions">
          <button className="secondary-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="add-stock-button" onClick={submit} disabled={busy}>
            {busy ? "Saving..." : deal ? "Update Deal" : "Create Deal"}
          </button>
        </div>
      </div>
    </div>
  );
}
