import { useEffect, useState } from "react";
import { formatMoney } from "../utils/money";
import { api } from "../services/api";
import type { DashboardOverview } from "../types";

export function Dashboard() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const result = await api.getDashboardOverview();
        setData(result);
        setError("");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load dashboard");
      } finally {
        setLoading(false);
      }
    }

    load();
    // Refresh every 30 seconds for live updates
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="dashboard-page">
        <div className="page-header">
          <div>
            <p className="eyebrow">OVERVIEW</p>
            <h1>Dashboard</h1>
          </div>
        </div>
        <div className="loading">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-page">
        <div className="page-header">
          <div>
            <p className="eyebrow">OVERVIEW</p>
            <h1>Dashboard</h1>
          </div>
        </div>
        <div className="error-box">{error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="dashboard-page">
        <div className="page-header">
          <div>
            <p className="eyebrow">OVERVIEW</p>
            <h1>Dashboard</h1>
          </div>
        </div>
        <div className="loading">No data available</div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div>
          <p className="eyebrow">OVERVIEW</p>
          <h1>Today's Dashboard</h1>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="dashboard-cards">
        <div className="dashboard-card">
          <p className="dashboard-label">Sales</p>
          <h2 className="dashboard-value">
            {formatMoney(data.sales)}
          </h2>
        </div>

        <div className="dashboard-card">
          <p className="dashboard-label">Orders</p>
          <h2 className="dashboard-value">{data.orders}</h2>
        </div>

        <div className="dashboard-card">
          <p className="dashboard-label">Cancelled</p>
          <h2 className="dashboard-value">{data.cancelled}</h2>
        </div>

        <div className="dashboard-card">
          <p className="dashboard-label">Low Stock</p>
          <h2 className="dashboard-value">{data.low_stock} Items</h2>
        </div>
      </div>

      {/* Hourly Sales Chart */}
      <div className="dashboard-section">
        <div className="section-header">
          <h3>Hourly Sales</h3>
        </div>
        <div className="chart-container">
          <div className="hourly-chart">
            {data.hourly_sales.map((item) => {
              const maxSale = Math.max(...data.hourly_sales.map(s => Number(s.revenue)));
              const height = maxSale === 0 ? 0 : (Number(item.revenue) / maxSale) * 100;
              const hour = String(item.hour).padStart(2, "0");

              return (
                <div key={item.hour} className="chart-bar">
                  <div className="bar-container">
                    <div
                      className="bar"
                      style={{ height: `${height}%` }}
                      title={`${hour}:00 - ${formatMoney(item.revenue)}`}
                    />
                  </div>
                  <span className="bar-label">{hour}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Top Selling Products */}
      <div className="dashboard-section">
        <div className="section-header">
          <h3>Top Selling Products</h3>
        </div>
        {data.top_products.length === 0 ? (
          <div className="empty-state">No sales today</div>
        ) : (
          <div className="top-products">
            <div className="products-head">
              <span>Rank</span>
              <span>Product</span>
              <span>Quantity</span>
              <span>Revenue</span>
            </div>
            {data.top_products.map((product, index) => (
              <div className="products-row" key={index}>
                <span className="rank">#{index + 1}</span>
                <span className="product-name">{product.product_name}</span>
                <span>{product.quantity_sold}</span>
                <span className="revenue">
                  {formatMoney(product.revenue)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
