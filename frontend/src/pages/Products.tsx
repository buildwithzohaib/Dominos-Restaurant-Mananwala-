import { Plus, Search, Edit2, Power, PowerOff, Lock, FolderOpen, Trash2 } from "lucide-react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { useState, useMemo, useEffect } from "react";

import { AddProductModal } from "../components/AddProductModal";
import { EditProductModal } from "../components/EditProductModal";
import { StatusBadge } from "../components/StatusBadge";
import { CategoryListModal } from "../components/CategoryListModal";
import { DealForm } from "../components/DealForm";
import { useCatalog } from "../context/CatalogContext";
import { api } from "../services/api";

import type { Product, DealOut } from "../types";

export function Products() {
  const formatCurrency = useCurrencyFormat();
  const { allProducts, allCategories, refresh, isLoading } = useCatalog();
  const [tab, setTab] = useState<"products" | "deals">("products");
  const [query, setQuery] = useState("");
  const [showDisabled, setShowDisabled] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [manageCategoriesOpen, setManageCategoriesOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [deals, setDeals] = useState<DealOut[]>([]);
  const [dealsLoading, setDealsLoading] = useState(false);
  const [addDealOpen, setAddDealOpen] = useState(false);
  const [editingDeal, setEditingDeal] = useState<DealOut | null>(null);

  // Load deals when tab changes or search/filter changes
  useEffect(() => {
    if (tab === "deals") {
      loadDeals();
    }
  }, [tab, query, showDisabled]);

  async function loadDeals() {
    setDealsLoading(true);
    try {
      const list = await api.getDeals(query.trim() || undefined, showDisabled);
      setDeals(list);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not load deals");
    } finally {
      setDealsLoading(false);
    }
  }

  async function deleteDeal(deal: DealOut) {
    if (!confirm(`Delete deal "${deal.name_display}"?`)) return;
    try {
      await api.deleteDeal(deal.id);
      await loadDeals();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not delete deal");
    }
  }

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
      <div className="page-header-toolbar">
        <div className="page-header">
          <div>
            <p className="eyebrow">CATALOG</p>
            <h1>Products & Deals</h1>
          </div>
        </div>

        <div className="inventory-toolbar">
          <div className="search-box">
            <Search size={18} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={tab === "products" ? "Search products..." : "Search deals..."}
            />
          </div>

          <div className="inventory-actions">
            <button
              className="secondary-button"
              onClick={() => setManageCategoriesOpen(true)}
            >
              <FolderOpen size={15} /> Manage Categories
            </button>

            <button
              className={showDisabled ? "secondary-button active" : "secondary-button"}
              onClick={() => setShowDisabled(!showDisabled)}
            >
              <Lock size={15} /> {showDisabled ? "Hide Disabled" : "Show Disabled"}
            </button>

            {tab === "products" ? (
              <button className="add-stock-button" onClick={() => setAddOpen(true)}>
                <Plus size={16} /> Add Product
              </button>
            ) : (
              <button className="add-stock-button" onClick={() => setAddDealOpen(true)}>
                <Plus size={16} /> Add Deal
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="tab-buttons">
        <button
          className={tab === "products" ? "tab-button active" : "tab-button"}
          onClick={() => setTab("products")}
        >
          Products
        </button>
        <button
          className={tab === "deals" ? "tab-button active" : "tab-button"}
          onClick={() => setTab("deals")}
        >
          Deals
        </button>
      </div>

      <div className="inventory-card">
        {tab === "products" ? (
          <>
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
          </>
        ) : (
          <>
            {dealsLoading ? (
              <div className="loading">Loading deals...</div>
            ) : !deals.length ? (
              <div className="loading">No deals found.</div>
            ) : (
              <>
                <div className="inventory-head">
                  <span>Deal</span>
                  <span>Category</span>
                  <span>Components</span>
                  <span>Price</span>
                  <span>Status</span>
                  <span />
                </div>

                {deals.map((deal) => (
                  <div
                    className={`inventory-row ${!deal.available ? "disabled-row" : ""}`}
                    key={deal.id}
                  >
                    <span>
                      <strong className="item-name">{deal.name_display}</strong>
                    </span>
                    <span>{deal.category.name_display}</span>
                    <span>{deal.components.length} item{deal.components.length !== 1 ? "s" : ""}</span>
                    <span>{formatCurrency(deal.price)}</span>
                    <span>
                      {deal.available ? (
                        <span className="badge">Active</span>
                      ) : (
                        <span className="badge disabled">Disabled</span>
                      )}
                    </span>
                    <span className="row-actions">
                      <button
                        className="row-action-button"
                        onClick={() => setEditingDeal(deal)}
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        className="row-action-button"
                        onClick={() => deleteDeal(deal)}
                        title="Delete deal"
                      >
                        <Trash2 size={16} />
                      </button>
                    </span>
                  </div>
                ))}
              </>
            )}
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

      {manageCategoriesOpen && (
        <CategoryListModal onClose={() => setManageCategoriesOpen(false)} />
      )}

      {addDealOpen && (
        <DealForm
          categories={allCategories}
          onClose={() => setAddDealOpen(false)}
          onSaved={() => {
            setAddDealOpen(false);
            loadDeals();
          }}
        />
      )}

      {editingDeal && (
        <DealForm
          deal={editingDeal}
          categories={allCategories}
          onClose={() => setEditingDeal(null)}
          onSaved={() => {
            setEditingDeal(null);
            loadDeals();
          }}
        />
      )}
    </div>
  );
}
