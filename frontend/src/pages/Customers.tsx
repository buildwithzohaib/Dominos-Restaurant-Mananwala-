import { Search, Edit2, Power, PowerOff, Lock, Loader, Users } from "lucide-react";
import { useState, useEffect } from "react";
import { api } from "../services/api";
import { EditCustomerModal } from "../components/EditCustomerModal";
import type { Customer, CustomerSearchResult } from "../types";

export function Customers() {
  const [query, setQuery] = useState("");
  const [showDisabled, setShowDisabled] = useState(false);
  const [results, setResults] = useState<CustomerSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<CustomerSearchResult | null>(null);
  const [totalCustomersCount, setTotalCustomersCount] = useState(0);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(async () => {
      setIsLoading(true);
      setError("");

      try {
        const data = await api.searchCustomers(query, showDisabled);
        setResults(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Search failed");
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [query, showDisabled]);

  // Load total count on mount
  useEffect(() => {
    async function loadCount() {
      try {
        const all = await api.searchCustomers("", false);
        setTotalCustomersCount(all.length);
      } catch {
        // Silent fail for total count
      }
    }
    loadCount();
  }, []);

  async function toggleCustomer(customer: CustomerSearchResult) {
    try {
      if (customer.is_active) {
        await api.deactivateCustomer(customer.id);
      } else {
        await api.activateCustomer(customer.id);
      }

      // Refresh search results
      const data = await api.searchCustomers(query, showDisabled);
      setResults(data);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Could not update customer");
    }
  }

  const hasResults = results.length > 0;
  const hasSearchQuery = query.trim().length > 0;
  const allCustomersEmpty = totalCustomersCount === 0 && !hasSearchQuery;

  return (
    <div className="products-page">
      <div className="page-header-toolbar">
        <div className="page-header">
          <div>
            <p className="eyebrow">OPERATIONS</p>
            <h1>Customers</h1>
          </div>
        </div>

        <div className="inventory-toolbar">
          <div className="search-box">
            <Search size={18} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search customers..."
            />
          </div>

          <div className="inventory-actions">
            <button
              className={
                showDisabled ? "secondary-button active" : "secondary-button"
              }
              onClick={() => setShowDisabled(!showDisabled)}
            >
              <Lock size={15} /> {showDisabled ? "Hide Disabled" : "Show Disabled"}
            </button>
          </div>
        </div>
      </div>

      <div className="inventory-card">
        {allCustomersEmpty ? (
          <div className="loading">
            <Users size={48} style={{ marginBottom: "16px", opacity: 0.3 }} />
            <p>No customers yet.</p>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
              Customers appear here when they are created via the POS.
            </p>
          </div>
        ) : isLoading ? (
          <div className="loading">
            <Loader size={24} className="spinner" />
            Loading customers...
          </div>
        ) : !hasResults ? (
          <div className="loading">
            <p>No customers match your search.</p>
          </div>
        ) : error ? (
          <div className="error-box">{error}</div>
        ) : (
          <>
            <div className="inventory-head">
              <span>Name</span>
              <span>Phone</span>
              <span>Address</span>
              <span>Orders</span>
              <span>Status</span>
              <span />
            </div>

            {results.map((customer) => (
              <div
                className={`inventory-row ${
                  !customer.is_active ? "disabled-row" : ""
                }`}
                key={customer.id}
              >
                <span>
                  <strong className="item-name">
                    {customer.name_display}
                  </strong>
                </span>

                <span>{customer.phone_raw || "—"}</span>

                <span
                  title={customer.address || ""}
                  style={{
                    maxWidth: "200px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {customer.address || "—"}
                </span>

                <span
                  title={`${customer.paid_order_count} paid of ${customer.order_count} total orders`}
                >
                  {customer.order_count === 0
                    ? "—"
                    : `${customer.paid_order_count}/${customer.order_count}`}
                </span>

                <span>
                  {customer.is_active ? (
                    <span className="badge active">Active</span>
                  ) : (
                    <span className="badge disabled">Disabled</span>
                  )}
                </span>

                <span className="row-actions">
                  <button
                    className="row-action-button"
                    onClick={() => setEditing(customer)}
                    title="Edit"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    className="row-action-button"
                    onClick={() => toggleCustomer(customer)}
                    title={
                      customer.is_active ? "Disable" : "Enable"
                    }
                  >
                    {customer.is_active ? (
                      <Power size={16} />
                    ) : (
                      <PowerOff size={16} />
                    )}
                  </button>
                </span>
              </div>
            ))}
          </>
        )}
      </div>

      {editing && (
        <EditCustomerModal
          customer={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            // Refresh results
            (async () => {
              try {
                const data = await api.searchCustomers(query, showDisabled);
                setResults(data);
              } catch {
                // Silent fail
              }
            })();
          }}
        />
      )}
    </div>
  );
}
