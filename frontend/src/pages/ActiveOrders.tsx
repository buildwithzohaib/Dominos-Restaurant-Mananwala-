import { useEffect, useState } from "react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { parseServerDate } from "../utils/dates";
import { api } from "../services/api";
import type { Order } from "../types";

export function ActiveOrders({ onResume }: { onResume: (order: Order) => void }) {
  const formatCurrency = useCurrencyFormat();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      setOrders(await api.getOrders({ status: "OPEN" }));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load orders");
    } finally {
      setLoading(false);
    }
  }

  // Load on mount and refresh every 30s
  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  function formatElapsedTime(createdAt: string): string {
    const created = parseServerDate(createdAt);
    const now = new Date();
    const diffMs = now.getTime() - created.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;

    if (diffHours > 0) {
      return `${diffHours}h ${mins}m`;
    }
    return `${diffMins}m`;
  }

  function getTotalQuantity(order: Order): number {
    return order.items.reduce((sum, item) => sum + item.quantity, 0);
  }

  function getPendingQuantity(order: Order): number {
    return order.items
      .filter((item) => item.batch_id === null)
      .reduce((sum, item) => sum + item.quantity, 0);
  }

  function getStatusBadge(order: Order) {
    const pending = getPendingQuantity(order);
    if (pending === 0) {
      return <span className="status-badge in-stock">All sent</span>;
    }
    return <span className="status-badge low-stock">{pending} pending</span>;
  }

  return (
    <div className="orders-page">
      <div className="page-header">
        <div>
          <p className="eyebrow">SERVICE</p>
          <h1>Active Orders</h1>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="orders-card">
        {loading ? (
          <div className="loading">Loading active orders...</div>
        ) : !orders.length ? (
          <div className="loading">No active orders.</div>
        ) : (
          <div className="orders-table active-orders-table">
            <div className="orders-head">
              <span>Table</span>
              <span>Items</span>
              <span>Elapsed</span>
              <span>Total</span>
              <span>Status</span>
              <span />
            </div>

            {orders.map((o) => (
              <div className="orders-row" key={o.id}>
                <div className="active-orders-table-cell">
                  <strong>{o.table?.name || "—"}</strong>
                  <span className="active-orders-order-number">{o.order_number}</span>
                </div>
                <span className="active-orders-items">{getTotalQuantity(o)}</span>
                <span className="active-orders-elapsed">{formatElapsedTime(o.created_at)}</span>
                <strong className="active-orders-total">{formatCurrency(o.total)}</strong>
                <span>{getStatusBadge(o)}</span>
                <button
                  className="row-action-button"
                  onClick={() => onResume(o)}
                >
                  Resume
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
