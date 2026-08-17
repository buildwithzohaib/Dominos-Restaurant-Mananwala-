import { useState } from "react";
import { X, Upload } from "lucide-react";
import { api, API_URL } from "../services/api";
import { rupeesToPaisa, paisaToRupees } from "../utils/money";
import { useCatalog } from "../context/CatalogContext";
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
  const { refresh } = useCatalog();
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
  const [uploadingImage, setUploadingImage] = useState(false);
  const [imageError, setImageError] = useState("");
  const [currentImageHash, setCurrentImageHash] = useState(product.image_hash);
  const [confirmDeleteImage, setConfirmDeleteImage] = useState(false);
  const [deletingImage, setDeletingImage] = useState(false);

  const [priceText, setPriceText] = useState(
    formData.price !== undefined ? String(paisaToRupees(formData.price)) : ""
  );
  const [purchasePriceText, setPurchasePriceText] = useState(
    formData.purchase_price !== undefined ? String(paisaToRupees(formData.purchase_price)) : ""
  );

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingImage(true);
    setImageError("");
    try {
      const updated = await api.uploadProductImage(product.id, file);
      setCurrentImageHash(updated.image_hash);
      // Refresh catalog so all views (ProductCard, etc.) update with new image
      await refresh();
    } catch (err) {
      setImageError(err instanceof Error ? err.message : "Could not upload image");
    } finally {
      setUploadingImage(false);
      // Reset the input so the same file can be uploaded again if needed
      e.target.value = "";
    }
  }

  async function handleDeleteImage() {
    setDeletingImage(true);
    setImageError("");
    try {
      await api.deleteProductImage(product.id);
      setCurrentImageHash(undefined);
      setConfirmDeleteImage(false);
      // Refresh catalog so all views (ProductCard, etc.) update without image
      await refresh();
    } catch (err) {
      setImageError(err instanceof Error ? err.message : "Could not delete image");
    } finally {
      setDeletingImage(false);
    }
  }

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

        {product.image && (
          <div style={{ marginTop: "12px", marginBottom: "12px" }}>
            <p className="modal-label">Current image:</p>
            <div className="image-preview-wrapper">
              <img
                src={`${API_URL}/images/${product.image}?v=${currentImageHash}`}
                alt={product.name_display}
                className="image-preview"
              />
              {!confirmDeleteImage && (
                <button
                  className="image-delete-button"
                  onClick={() => setConfirmDeleteImage(true)}
                  disabled={deletingImage}
                  title="Remove image"
                >
                  ✕
                </button>
              )}
            </div>
            {confirmDeleteImage && (
              <div className="image-delete-confirm-block">
                <span>Remove this photo?</span>
                <div className="image-delete-actions">
                  <button
                    className="secondary-button"
                    onClick={() => setConfirmDeleteImage(false)}
                    disabled={deletingImage}
                  >
                    Cancel
                  </button>
                  <button
                    className="pay-button danger"
                    onClick={handleDeleteImage}
                    disabled={deletingImage}
                  >
                    {deletingImage ? "Removing..." : "Remove"}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {imageError && <div className="error-box">{imageError}</div>}

        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 12px",
            border: "1px solid #e2e6ec",
            borderRadius: "6px",
            cursor: uploadingImage ? "not-allowed" : "pointer",
            opacity: uploadingImage ? 0.6 : 1,
            marginBottom: "12px",
          }}
        >
          <Upload size={18} />
          <span style={{ fontSize: "14px" }}>
            {uploadingImage ? "Uploading..." : "Upload Product Image (JPEG/PNG)"}
          </span>
          <input
            type="file"
            accept="image/jpeg,image/png"
            onChange={handleImageUpload}
            disabled={uploadingImage}
            style={{ display: "none" }}
          />
        </label>

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
