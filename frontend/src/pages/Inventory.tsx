import { History, Plus, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";

import { AddStockModal } from "../components/AddStockModal";
import { EditInventoryModal } from "../components/EditInventoryModal";
import { StatusBadge } from "../components/StatusBadge";
import { StockAdjustmentModal } from "../components/StockAdjustmentModal";
import { StockHistory } from "../components/StockHistory";

import { api } from "../services/api";
import type { Product } from "../types";

export function Inventory({ onChange }: { onChange?: () => void }) {
  const [items, setItems] = useState<Product[]>([]);
  // Full, unfiltered product list — kept separate from the (possibly search-narrowed)
  // `items` above so the Add Stock / Stock Adjustment product pickers always offer
  // every item, not just whatever the inventory search happens to be showing.
  const [allItems, setAllItems] = useState<Product[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<"table" | "history">("table");
  const [addOpen, setAddOpen] = useState(false);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);

  async function load(search: string) {
    setLoading(true);
    try {
      setItems(await api.getInventory(search));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load inventory");
    } finally {
      setLoading(false);
    }
  }

  async function loadAll() {
    try {
      setAllItems(await api.getInventory());
    } catch {
      // Surfaced already via the main table's own load() error box.
    }
  }

  // Debounced server-side search — item name or SKU, no full-page reload.
  useEffect(() => {
    const timer = setTimeout(() => load(query), 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  useEffect(() => {
    loadAll();
  }, []);

  function applyUpdated(updated: Product) {
    setItems((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    setAllItems((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    onChange?.();
  }

  return (
    <div className="inventory-page">
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

          <button className="add-stock-button" onClick={() => setAddOpen(true)}>
            <Plus size={16} /> Add Stock
          </button>
        </div>
      </div>

      {error && view === "table" && <div className="error-box">{error}</div>}

      {view === "history" ? (
        <StockHistory />
      ) : (
        <div className="inventory-card">
          {loading ? (
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
                    <strong className="item-name">{item.name}</strong>
                  </span>
                  <span>{item.sku}</span>
                  <span>{item.stock}</span>
                  <span>{item.min_stock}</span>
                  <span>{item.unit}</span>
                  <span>Rs. {Number(item.purchase_price).toFixed(2)}</span>
                  <span>Rs. {Number(item.price).toFixed(2)}</span>
                  <span>
                    <StatusBadge status={item.stock_status} />
                  </span>
                  <span>{new Date(item.updated_at).toLocaleString()}</span>
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
          products={allItems}
          onClose={() => setAddOpen(false)}
          onSaved={(updated) => {
            applyUpdated(updated);
            setAddOpen(false);
          }}
        />
      )}

      {adjustOpen && (
        <StockAdjustmentModal
          products={allItems}
          onClose={() => setAdjustOpen(false)}
          onSaved={(updated) => {
            applyUpdated(updated);
            setAdjustOpen(false);
          }}
        />
      )}

      {editing && (
        <EditInventoryModal
          product={editing}
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
