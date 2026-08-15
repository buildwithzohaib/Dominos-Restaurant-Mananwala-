import { Plus, Search, Edit2, Power, Lock } from "lucide-react";
import { formatMoney } from "../utils/money";
import { useEffect, useState } from "react";

import { AddProductModal } from "../components/AddProductModal";
import { EditProductModal } from "../components/EditProductModal";
import { StatusBadge } from "../components/StatusBadge";

import { api } from "../services/api";
import type { Product } from "../types";

export function Products() {
  const [items, setItems] = useState<Product[]>([]);
  const [allItems, setAllItems] = useState<Product[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [showDisabled, setShowDisabled] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setItems(
        await api.getProducts(
          query || undefined,
          showDisabled
        )
      );
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load products");
    } finally {
      setLoading(false);
    }
  }

  async function loadAll() {
    try {
      setAllItems(await api.getProducts(undefined, true));
    } catch {
      // Error already surfaced in main load
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => load(), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, showDisabled]);

  useEffect(() => {
    loadAll();
  }, []);

  function applyUpdated(updated: Product) {
    setItems((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    setAllItems((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  }

  async function toggleProduct(product: Product) {
    try {
      if (product.available) {
        const updated = await api.disableProduct(product.id);
        applyUpdated(updated);
      } else {
        const updated = await api.enableProduct(product.id);
        applyUpdated(updated);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not update product");
    }
  }

  return (
    <div className="products-page">
      <div className="page-header">
        <div>
          <p className="eyebrow">CATALOG</p>
          <h1>Products</h1>
        </div>
      </div>

      <div className="inventory-toolbar">
        <div className="search-box">
          <Search size={18} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search products..."
          />
        </div>

        <div className="inventory-actions">
          <button
            className={showDisabled ? "secondary-button active" : "secondary-button"}
            onClick={() => setShowDisabled(!showDisabled)}
          >
            <Lock size={15} /> {showDisabled ? "Hide Disabled" : "Show Disabled"}
          </button>

          <button className="add-stock-button" onClick={() => setAddOpen(true)}>
            <Plus size={16} /> Add Product
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="inventory-card">
        {loading ? (
          <div className="loading">Loading products...</div>
        ) : !items.length ? (
          <div className="loading">No products found.</div>
        ) : (
          <>
            <div className="inventory-head">
              <span>Product</span>
              <span>Category</span>
              <span>SKU</span>
              <span>Selling Price</span>
              <span>Stock</span>
              <span>Status</span>
              <span />
            </div>

            {items.map((item) => (
              <div
                className={`inventory-row ${!item.available ? "disabled-row" : ""}`}
                key={item.id}
              >
                <span>
                  <strong className="item-name">{item.name}</strong>
                </span>
                <span>
                  {item.category_id} {/* TODO: display category name */}
                </span>
                <span>{item.sku}</span>
                <span>{formatMoney(item.price)}</span>
                <span>{item.stock}</span>
                <span>
                  {item.available ? (
                    <StatusBadge status={item.stock_status} />
                  ) : (
                    <span className="badge disabled">Disabled</span>
                  )}
                </span>
                <span className="row-actions">
                  <button
                    className="row-action-button"
                    onClick={() => setEditing(item)}
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    className="row-action-button"
                    onClick={() => toggleProduct(item)}
                  >
                    <Power size={16} />
                  </button>
                </span>
              </div>
            ))}
          </>
        )}
      </div>

      {addOpen && (
        <AddProductModal
          categories={[]} // TODO: fetch categories
          onClose={() => setAddOpen(false)}
          onSaved={(created) => {
            applyUpdated(created);
            setAddOpen(false);
          }}
        />
      )}

      {editing && (
        <EditProductModal
          product={editing}
          categories={[]} // TODO: fetch categories
          onClose={() => setEditing(null)}
          onSaved={(updated) => {
            applyUpdated(updated);
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}
