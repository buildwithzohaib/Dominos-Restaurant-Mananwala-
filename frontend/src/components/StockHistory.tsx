import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../services/api";
import type { StockMovement } from "../types";

export function StockHistory() {
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [search, setSearch] = useState("");
  const [movementType, setMovementType] = useState<"" | "PURCHASE" | "ADJUSTMENT" | "SALE" | "CANCELLATION">("");
  const [date, setDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(true);
      api
        .getStockMovements({ search, movement_type: movementType || undefined, date: date || undefined })
        .then((rows) => {
          setMovements(rows);
          setError("");
        })
        .catch((e) => setError(e instanceof Error ? e.message : "Could not load stock history"))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timer);
  }, [search, movementType, date]);

  return (
    <div className="stock-history">
      <div className="stock-history-toolbar">
        <div className="search-box">
          <Search size={18} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by item or supplier..."
          />
        </div>

        <select
          className="table-select"
          value={movementType}
          onChange={(e) => setMovementType(e.target.value as "" | "PURCHASE" | "ADJUSTMENT" | "SALE" | "CANCELLATION")}
        >
          <option value="">All Types</option>
          <option value="PURCHASE">Purchase</option>
          <option value="ADJUSTMENT">Adjustment</option>
          <option value="SALE">Sale</option>
          <option value="CANCELLATION">Cancellation</option>
        </select>

        <input
          className="table-select"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="inventory-card">
        {loading ? (
          <div className="loading">Loading stock history...</div>
        ) : !movements.length ? (
          <div className="loading">No stock movements found.</div>
        ) : (
          <>
            <div className="history-head">
              <span>Date</span>
              <span>Item</span>
              <span>Change</span>
              <span>Reason</span>
              <span>Supplier</span>
              <span>Before</span>
              <span>After</span>
              <span>Purchase Price</span>
              <span>Reference</span>
            </div>

            {movements.map((m) => (
              <div className="history-row" key={m.id}>
                <span>{new Date(m.created_at).toLocaleString()}</span>
                <span>{m.product_name}</span>
                <span className={m.quantity_change > 0 ? "change-positive" : "change-negative"}>
                  {m.quantity_change > 0 ? `+${m.quantity_change}` : m.quantity_change}
                </span>
                <span>{m.reason}</span>
                <span>{m.supplier ?? "—"}</span>
                <span>{m.stock_before}</span>
                <span>{m.stock_after}</span>
                <span>{m.purchase_price != null ? `Rs. ${Number(m.purchase_price).toFixed(2)}` : "—"}</span>
                <span>{m.reference ?? "—"}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
