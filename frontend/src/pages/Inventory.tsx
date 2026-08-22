import { History, Plus, Search, SlidersHorizontal } from "lucide-react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { useState, useMemo, useEffect } from "react";

import { AddStockModal } from "../components/AddStockModal";
import { EditInventoryModal } from "../components/EditInventoryModal";
import { StatusBadge } from "../components/StatusBadge";
import { StockAdjustmentModal } from "../components/StockAdjustmentModal";
import { StockHistory } from "../components/StockHistory";
import { StockReconciliationForm } from "../components/StockReconciliationForm";
import { useCatalog } from "../context/CatalogContext";
import { parseServerDate } from "../utils/dates";

import type { Product } from "../types";

export function Inventory({ showLowStockOnly: initialShowLowStock }: { showLowStockOnly?: boolean } = {}) {
  const formatCurrency = useCurrencyFormat();
  const { allProducts, refresh, isLoading } = useCatalog();
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"table" | "history" | "reconcile">("table");
  const [showLowStockOnly, setShowLowStockOnly] = useState(initialShowLowStock ?? false);

  // Apply initial low stock filter if passed as a prop
  useEffect(() => {
    if (initialShowLowStock) {
      setShowLowStockOnly(true);
    }
  }, [initialShowLowStock]);
  const [addOpen, setAddOpen] = useState(false);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);

  // Filter products locally: by search query (name or SKU, case-insensitive) and low-stock status
  const items = useMemo(() => {
    let filtered = allProducts;

    // Apply low-stock filter if enabled
    if (showLowStockOnly) {
      filtered = filtered.filter(
        (p) => p.stock_status === "LOW_STOCK" || p.stock_status === "OUT_OF_STOCK"
      );
    }

    // Apply search filter if query is not empty
    if (!query.trim()) return filtered;

    const lowerQuery = query.toLowerCase();
    return filtered.filter(
      (p) =>
        p.name_display.toLowerCase().includes(lowerQuery) ||
        p.sku.toLowerCase().includes(lowerQuery)
    );
  }, [allProducts, query, showLowStockOnly]);

  return (
    <div className="inventory-page">
      <div className="page-header-toolbar">
        <div className="page-header">
          <div>
            <p className="eyebrow">STOCK</p>
            <h1>Inventory</h1>
          </div>
        </div>

        <div className="inventory-toolbar">
          <div className="search-box">
            <Search size={18} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search inventory..."
            />
          </div>

          <label className="low-stock-filter">
            <input
              type="checkbox"
              checked={showLowStockOnly}
              onChange={(e) => setShowLowStockOnly(e.target.checked)}
            />
            Show only low stock
          </label>

          <div className="inventory-actions">
            <button
              className="secondary-button"
              onClick={() => setAdjustOpen(true)}
            >
              <SlidersHorizontal size={15} /> Stock Adjustment
            </button>

            <button
              className={view === "history" ? "secondary-button active" : "secondary-button"}
              onClick={() => setView((v) => (v === "history" ? "table" : "history"))}
            >
              <History size={15} /> {view === "history" ? "Back to Inventory" : "Stock History"}
            </button>

            <button
              className={view === "reconcile" ? "secondary-button active" : "secondary-button"}
              onClick={() => setView((v) => (v === "reconcile" ? "table" : "reconcile"))}
            >
              {view === "reconcile" ? "Back to Inventory" : "Reconcile Stock"}
            </button>

            <button className="add-stock-button" onClick={() => setAddOpen(true)}>
              <Plus size={16} /> Add Stock
            </button>
          </div>
        </div>
      </div>

      {view === "history" ? (
        <StockHistory />
      ) : view === "reconcile" ? (
        <StockReconciliationForm
          products={allProducts}
          onClose={() => setView("table")}
          onSaved={() => {
            setView("table");
            refresh();
          }}
        />
      ) : (
        <div className="inventory-card">
          {isLoading ? (
            <div className="loading">Loading inventory...</div>
          ) : !items.length ? (
            <div className="loading">No inventory items found.</div>
          ) : (
            <>
              <div className="inventory-head">
                <span>Item</span>
                <span>SKU</span>
                <span>Stock</span>
                <span>Min</span>
                <span>Unit</span>
                <span>Purchase</span>
                <span>Selling</span>
                <span>Status</span>
                <span>Updated</span>
                <span />
              </div>

              {items.map((item) => (
                <div className="inventory-row" key={item.id}>
                  <span>
                    <strong className="item-name">{item.name_display}</strong>
                  </span>
                  <span>{item.sku}</span>
                  <span>{item.stock}</span>
                  <span>{item.min_stock}</span>
                  <span>{item.unit}</span>
                  <span>{formatCurrency(item.purchase_price)}</span>
                  <span>{formatCurrency(item.price)}</span>
                  <span>
                    <StatusBadge status={item.stock_status} />
                  </span>
                  <span>{parseServerDate(item.updated_at).toLocaleString()}</span>
                  <span>
                    <button
                      className="row-action-button"
                      onClick={() => setEditing(item)}
                    >
                      Edit
                    </button>
                  </span>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {addOpen && (
        <AddStockModal
          products={allProducts}
          onClose={() => setAddOpen(false)}
          onSaved={() => {
            setAddOpen(false);
            refresh();
          }}
        />
      )}

      {adjustOpen && (
        <StockAdjustmentModal
          products={allProducts}
          onClose={() => setAdjustOpen(false)}
          onSaved={() => {
            setAdjustOpen(false);
            refresh();
          }}
        />
      )}

      {editing && (
        <EditInventoryModal
          product={editing}
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
