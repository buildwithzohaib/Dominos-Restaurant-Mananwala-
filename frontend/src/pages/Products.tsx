import { Plus, Search, Edit2, Power, PowerOff, Lock } from "lucide-react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { useState, useMemo } from "react";

import { AddProductModal } from "../components/AddProductModal";
import { EditProductModal } from "../components/EditProductModal";
import { StatusBadge } from "../components/StatusBadge";
import { useCatalog } from "../context/CatalogContext";
import { api } from "../services/api";

import type { Product } from "../types";

export function Products() {
  const formatCurrency = useCurrencyFormat();
  const { allProducts, allCategories, refresh, isLoading } = useCatalog();
  const [query, setQuery] = useState("");
  const [showDisabled, setShowDisabled] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);

  // Filter products locally: by search and by availability
  const items = useMemo(() => {
    let filtered = allProducts;

    // Filter by search query (match on name_display, case-insensitive)
    if (query.trim()) {
      const lowerQuery = query.toLowerCase();
      filtered = filtered.filter((p) =>
        p.name_display.toLowerCase().includes(lowerQuery)
      );
    }

    // Filter by availability
    if (!showDisabled) {
      filtered = filtered.filter((p) => p.available);
    }

    return filtered;
  }, [allProducts, query, showDisabled]);

  async function toggleProduct(product: Product) {
    try {
      if (product.available) {
        await api.disableProduct(product.id);
      } else {
        await api.enableProduct(product.id);
      }
      await refresh();
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

      <div className="inventory-card">
        {isLoading ? (
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
                  <strong className="item-name">{item.name_display}</strong>
                </span>
                <span>
                  {item.category.name_display}
                </span>
                <span>{item.sku}</span>
                <span>{formatCurrency(item.price)}</span>
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
                    title={item.available ? "Disable" : "Enable"}
                  >
                    {item.available ? <Power size={16} /> : <PowerOff size={16} />}
                  </button>
                </span>
              </div>
            ))}
          </>
        )}
      </div>

      {addOpen && (
        <AddProductModal
          categories={allCategories}
          onClose={() => setAddOpen(false)}
          onSaved={() => {
            setAddOpen(false);
            refresh();
          }}
        />
      )}

      {editing && (
        <EditProductModal
          product={editing}
          categories={allCategories}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}
