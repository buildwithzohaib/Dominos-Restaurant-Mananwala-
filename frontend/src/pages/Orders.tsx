import { Search } from "lucide-react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { useEffect, useState } from "react";

import { CancelOrderModal } from "../components/CancelOrderModal";
import { OrderDetailsModal } from "../components/OrderDetailsModal";
import { OrderStatusBadge } from "../components/OrderStatusBadge";

import { api } from "../services/api";
import { parseServerDate } from "../utils/dates";
import type { Order, OrderStatus } from "../types";

export function Orders() {
  const formatCurrency = useCurrencyFormat();
  const [orders, setOrders] = useState<Order[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | OrderStatus>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [viewing, setViewing] = useState<Order | null>(null);
  const [cancelling, setCancelling] = useState<Order | null>(null);

  async function load() {
    setLoading(true);
    try {
      setOrders(await api.getOrders({ search, status: statusFilter || undefined }));
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load orders");
    } finally {
      setLoading(false);
    }
  }

  // Debounced server-side search/filter — order number, no full-page reload.
  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, statusFilter]);

  function applyUpdated(updated: Order) {
    setOrders((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
    setViewing(updated);
  }

  return (
    <div className="orders-page">
      <div className="page-header-toolbar">
        <div className="page-header">
          <div>
            <p className="eyebrow">SALES</p>
            <h1>Order History</h1>
          </div>
        </div>

        <div className="inventory-toolbar">
          <div className="search-box">
            <Search size={18} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by order number..."
            />
          </div>

          <div className="order-type-switcher">
            {(["", "PAID", "CANCELLED"] as const).map((value) => (
              <button
                key={value}
                className={statusFilter === value ? "active" : ""}
                onClick={() => setStatusFilter(value)}
              >
                {value === "" ? "All" : value === "PAID" ? "Paid" : "Cancelled"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="orders-card">
        {loading ? (
          <div className="loading">Loading orders...</div>
        ) : !orders.length ? (
          <div className="loading">No orders found.</div>
        ) : (
          <div className="orders-table">
            <div className="orders-head">
              <span>Order</span>
              <span>Date</span>
              <span>Customer</span>
              <span>Total</span>
              <span>Status</span>
              <span />
            </div>

            {orders.map((o) => (
              <div className="orders-row" key={o.id}>
                <strong>{o.order_number}</strong>
                <span>{parseServerDate(o.created_at).toLocaleString()}</span>
                <span>{o.customer?.name_display || "Walk-in"}</span>
                <strong>{formatCurrency(o.total)}</strong>
                <span>
                  <OrderStatusBadge status={o.status} />
                </span>
                <button className="row-action-button" onClick={() => setViewing(o)}>
                  View
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {viewing && (
        <OrderDetailsModal
          order={viewing}
          onClose={() => setViewing(null)}
          onCancelRequested={() => setCancelling(viewing)}
        />
      )}

      {cancelling && (
        <CancelOrderModal
          order={cancelling}
          onClose={() => setCancelling(null)}
          onCancelled={(updated) => {
            applyUpdated(updated);
            setCancelling(null);
          }}
        />
      )}
    </div>
  );
}
