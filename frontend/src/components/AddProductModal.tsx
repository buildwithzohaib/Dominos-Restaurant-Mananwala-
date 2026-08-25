import { useState } from "react";
import { X, Plus, Trash2 } from "lucide-react";
import { api } from "../services/api";
import { rupeesToPaisa, paisaToRupees } from "../utils/money";
import { useCatalog } from "../context/CatalogContext";
import type { Category, Product, ProductFormState, ProductCreateInput, ProductSizeInput } from "../types";

export function AddProductModal({
  categories,
  onClose,
  onSaved,
}: {
  categories: Category[];
  onClose: () => void;
  onSaved: (product: Product) => void;
}) {
  const { allCategories, refresh } = useCatalog();

  const [formData, setFormData] = useState<ProductFormState>({
    category_id: null,
    name: "",
    price: 100,
    purchase_price: 50,
    stock: 0,
    min_stock: 5,
    sku: "",
    unit: "Piece",
    has_sizes: false,
    sizes: [],
  });

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Category creation state (only used when no categories exist initially)
  const [newCategoryName, setNewCategoryName] = useState("");
  const [categoryCreationError, setCategoryCreationError] = useState("");
  const [creatingCategory, setCreatingCategory] = useState(false);

  const [priceText, setPriceText] = useState(String(paisaToRupees(formData.price)));
  const [purchasePriceText, setPurchasePriceText] = useState(
    formData.purchase_price ? String(paisaToRupees(formData.purchase_price)) : ""
  );

  async function createCategory() {
    const trimmed = newCategoryName.trim();
    if (!trimmed) {
      setCategoryCreationError("Category name cannot be empty");
      return;
    }

    setCreatingCategory(true);
    setCategoryCreationError("");
    try {
      const created = await api.createCategory(trimmed);
      setNewCategoryName("");
      await refresh();
      // Auto-select the newly created category
      setFormData({ ...formData, category_id: created.id });
    } catch (e) {
      setCategoryCreationError(e instanceof Error ? e.message : "Could not create category");
    } finally {
      setCreatingCategory(false);
    }
  }

  function addSize() {
    const newSize: ProductSizeInput = {
      name: "",
      price: 0,
      sort_order: formData.sizes.length + 1,
    };
    setFormData({
      ...formData,
      sizes: [...formData.sizes, newSize],
    });
  }

  function removeSize(index: number) {
    setFormData({
      ...formData,
      sizes: formData.sizes.filter((_, i) => i !== index),
    });
  }

  function updateSize(index: number, updates: Partial<ProductSizeInput>) {
    const updated = [...formData.sizes];
    updated[index] = { ...updated[index], ...updates };
    setFormData({ ...formData, sizes: updated });
  }

  async function submit() {
    if (formData.category_id === null) {
      setError("Please select a category");
      return;
    }

    if (formData.has_sizes) {
      if (formData.sizes.length === 0) {
        setError("Add at least one size when sizes are enabled");
        return;
      }
      for (const size of formData.sizes) {
        if (!size.name || !size.name.trim()) {
          setError("Size name cannot be empty");
          return;
        }
        if (size.price <= 0) {
          setError("Size price must be positive");
          return;
        }
      }
    }

    setBusy(true);
    setError("");
    try {
      const request: ProductCreateInput = {
        category_id: formData.category_id,
        name: formData.name,
        price: rupeesToPaisa(parseFloat(priceText) || 0),
        purchase_price: purchasePriceText ? rupeesToPaisa(parseFloat(purchasePriceText) || 0) : undefined,
        stock: formData.stock,
        min_stock: formData.min_stock,
        sku: formData.sku,
        unit: formData.unit,
        image: formData.image,
        sizes: formData.has_sizes ? formData.sizes : undefined,
      };
      const product = await api.createProduct(request);
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

        {allCategories.length === 0 ? (
          <div className="modal-category-create-section">
            <div className="error-box">
              <p>Create a category first</p>
            </div>

            <div className="category-create-input-row">
              <input
                type="text"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                placeholder="New category name"
                disabled={creatingCategory}
                onKeyDown={(e) => {
                  if (e.key === "Enter") createCategory();
                }}
              />
              <button
                type="button"
                className="add-stock-button"
                onClick={createCategory}
                disabled={creatingCategory || !newCategoryName.trim()}
              >
                {creatingCategory ? "Creating..." : "Create"}
              </button>
            </div>

            {categoryCreationError && (
              <div className="error-box">
                {categoryCreationError}
              </div>
            )}
          </div>
        ) : (
          <>
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
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span>Selling Price</span>
                  <label style={{ fontSize: "12px", fontWeight: "normal", display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={formData.has_sizes}
                      onChange={(e) =>
                        setFormData({ ...formData, has_sizes: e.target.checked, sizes: e.target.checked ? [] : formData.sizes })
                      }
                    />
                    Enable Sizes
                  </label>
                </div>
                <input
                  type="number"
                  step="0.01"
                  value={priceText}
                  onChange={(e) => setPriceText(e.target.value)}
                  disabled={formData.has_sizes}
                  style={{ opacity: formData.has_sizes ? 0.5 : 1 }}
                />
                {formData.has_sizes && (
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                    Sizes define the price for this product
                  </div>
                )}
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

            {formData.has_sizes && (
              <div style={{ marginTop: "20px" }}>
                <p className="modal-label">Sizes</p>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {formData.sizes.map((size, index) => (
                    <div key={index} style={{ display: "grid", gridTemplateColumns: "1fr 100px 40px", gap: "8px", alignItems: "end" }}>
                      <input
                        type="text"
                        placeholder="Size name (e.g., Small)"
                        value={size.name}
                        onChange={(e) => updateSize(index, { name: e.target.value })}
                        style={{ padding: "8px", border: "1px solid var(--border)", borderRadius: "6px", fontSize: "13px" }}
                      />
                      <input
                        type="number"
                        placeholder="Price"
                        step="0.01"
                        value={size.price > 0 ? paisaToRupees(size.price) : ""}
                        onChange={(e) =>
                          updateSize(index, { price: rupeesToPaisa(parseFloat(e.target.value) || 0) })
                        }
                        style={{ padding: "8px", border: "1px solid var(--border)", borderRadius: "6px", fontSize: "13px" }}
                      />
                      <button
                        type="button"
                        onClick={() => removeSize(index)}
                        style={{
                          padding: "6px",
                          background: "var(--danger-bg)",
                          color: "var(--danger-text)",
                          border: "none",
                          borderRadius: "6px",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                        title="Remove size"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={addSize}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "8px 12px",
                      background: "var(--surface-alt)",
                      color: "var(--text)",
                      border: "1px dashed var(--border)",
                      borderRadius: "6px",
                      cursor: "pointer",
                      fontSize: "13px",
                    }}
                  >
                    <Plus size={16} />
                    Add Size
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {error && <div className="error-box">{error}</div>}

        {allCategories.length > 0 && (
          <div className="modal-action-row">
            <button className="secondary-button" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button
              className="pay-button"
              disabled={busy || !formData.name || formData.category_id === null}
              onClick={submit}
            >
              {busy ? "Creating..." : "Create Product"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
