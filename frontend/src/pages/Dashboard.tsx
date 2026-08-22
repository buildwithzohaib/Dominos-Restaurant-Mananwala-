import { useEffect, useState } from "react";
import { LineChart, Line, AreaChart, Area, PieChart, Pie, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from "recharts";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { api } from "../services/api";
import type { DashboardRange } from "../types";

type RangeType = "today" | "7days" | "30days";

export function Dashboard() {
  const formatCurrency = useCurrencyFormat();
  const [range, setRange] = useState<RangeType>("today");
  const [data, setData] = useState<DashboardRange | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const result = await api.getDashboardRange(range);
        setData(result);
        setError("");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load dashboard");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [range]);

  const calculateChangePercent = (current: number, previous: number): string => {
    if (previous === 0) return "";
    const change = ((current - previous) / previous) * 100;
    if (Math.abs(change) > 999) return "";
    const sign = change > 0 ? "+" : "";
    return `${sign}${change.toFixed(0)}%`;
  };

  const getChangeDirection = (current: number, previous: number): string => {
    if (previous === 0) return "";
    return current >= previous ? "up" : "down";
  };

  if (loading) {
    return (
      <div className="dashboard-page">
        <div className="dashboard-header">
          <h1>Overview</h1>
        </div>
        <div className="loading">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-page">
        <div className="dashboard-header">
          <h1>Overview</h1>
        </div>
        <div className="error-box">{error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="dashboard-page">
        <div className="dashboard-header">
          <h1>Overview</h1>
        </div>
        <div className="loading">No data available</div>
      </div>
    );
  }

  const changePercent = calculateChangePercent(data.sales, data.sales_previous);
  const changeDirection = getChangeDirection(data.sales, data.sales_previous);

  // Prepare data for charts
  const dailySalesData = data.daily_sales.map(item => ({
    date: new Date(item.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    revenue: Math.round(item.revenue / 100)
  }));

  const orderTypeData = [
    { name: "Dine-in", value: data.dine_in_count, color: "#2a78d6" },
    { name: "Takeaway", value: data.takeaway_count, color: "#1baf7a" },
    { name: "Delivery", value: data.delivery_count, color: "#eb6834" }
  ];

  const topProductsData = data.top_products.map(item => ({
    name: item.product_name.length > 25 ? item.product_name.substring(0, 22) + "..." : item.product_name,
    qty: item.quantity_sold,
    revenue: Math.round(item.revenue / 100)
  }));

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <h1>Overview</h1>
        <div className="range-selector">
          <button
            className={`range-button ${range === "today" ? "active" : ""}`}
            onClick={() => setRange("today")}
          >
            Today
          </button>
          <button
            className={`range-button ${range === "7days" ? "active" : ""}`}
            onClick={() => setRange("7days")}
          >
            7d
          </button>
          <button
            className={`range-button ${range === "30days" ? "active" : ""}`}
            onClick={() => setRange("30days")}
          >
            30d
          </button>
        </div>
      </div>

      {/* KPI Grid - 8 tiles in 4x2 */}
      <div className="kpi-grid">
        {/* Sales */}
        <div className="kpi-tile">
          <p className="kpi-label">Sales</p>
          <p className="kpi-value">{formatCurrency(data.sales)}</p>
          <p className="kpi-context">
            {changePercent ? (
              <span className={`change ${changeDirection}`}>
                {changePercent} {range === "today" ? "vs yesterday" : "vs period"}
              </span>
            ) : (
              "no comparable period"
            )}
          </p>
        </div>

        {/* Profit */}
        <div className="kpi-tile">
          <p className="kpi-label">Profit</p>
          <p className="kpi-value">{formatCurrency(data.profit)}</p>
          <p className="kpi-context">
            {data.orders_missing_cost > 0
              ? `${data.orders_missing_cost} orders excluded`
              : `${(data.profit_margin_pct / 100).toFixed(1)}% margin`}
          </p>
        </div>

        {/* Orders */}
        <div className="kpi-tile">
          <p className="kpi-label">Orders</p>
          <p className="kpi-value">{data.orders}</p>
          <p className="kpi-context">avg {formatCurrency(data.average_order_value)}</p>
        </div>

        {/* Cash / Card */}
        <div className="kpi-tile">
          <p className="kpi-label">Cash / Card</p>
          <p className="kpi-value">{data.cash_orders} / {data.card_orders}</p>
          <p className="kpi-context">{formatCurrency(data.cash_sales)} cash</p>
        </div>

        {/* Discounts */}
        <div className="kpi-tile bordered-amber">
          <p className="kpi-label">Discounts</p>
          <p className="kpi-value">{formatCurrency(data.discount_total)}</p>
          <p className="kpi-context">{data.discount_order_count} orders</p>
        </div>

        {/* Cancelled */}
        <div className="kpi-tile bordered-red">
          <p className="kpi-label">Cancelled</p>
          <p className="kpi-value">{data.cancelled_count}</p>
          <p className="kpi-context danger">{formatCurrency(data.cancelled_value)}</p>
        </div>

        {/* Avg Bill */}
        <div className="kpi-tile">
          <p className="kpi-label">Avg Bill</p>
          <p className="kpi-value">{formatCurrency(data.average_order_value)}</p>
          <p className="kpi-context">&nbsp;</p>
        </div>

        {/* Low Stock */}
        <div className="kpi-tile bordered-amber">
          <p className="kpi-label">Low Stock</p>
          <p className="kpi-value">{data.low_stock_count}</p>
          <p className="kpi-context">items</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className={range === "today" ? "charts-row full-width" : "charts-row"}>
        {/* Daily Sales Chart */}
        {range !== "today" && (
          <div className="chart-panel">
            <h3 className="panel-title">Daily Sales</h3>
            <ResponsiveContainer width="100%" height={170}>
              <AreaChart data={dailySalesData} margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#F5B301" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#F5B301" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2c2f38" vertical={false} />
                <XAxis
                  dataKey="date"
                  stroke="#8b8fa3"
                  style={{ fontSize: "11px" }}
                  tick={{ fill: "#8b8fa3" }}
                  interval={Math.max(0, Math.floor(dailySalesData.length / 6))}
                />
                <YAxis
                  stroke="#8b8fa3"
                  style={{ fontSize: "11px" }}
                  tick={{ fill: "#8b8fa3" }}
                />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1c1f27", border: "1px solid #2c2f38", borderRadius: "6px" }}
                  labelStyle={{ color: "#f2f3f7" }}
                />
                <Area
                  type="linear"
                  dataKey="revenue"
                  stroke="#F5B301"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorRevenue)"
                  dot={false}
                  activeDot={{ fill: "#F5B301", r: 4 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Order Types Donut */}
        <div className="chart-panel donut-panel">
          <h3 className="panel-title">Order Types</h3>
          {data.orders === 0 ? (
            <div className="empty-state">No orders yet</div>
          ) : (
            <div className="donut-container">
              <div className="donut-chart-wrapper">
                <ResponsiveContainer width="100%" height={170}>
                  <PieChart>
                    <Pie
                      data={orderTypeData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={75}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {orderTypeData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: "#1c1f27", border: "1px solid #2c2f38", borderRadius: "6px" }}
                      labelStyle={{ color: "#f2f3f7" }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="donut-overlay">
                  <div className="donut-total">{data.orders}</div>
                  <div className="donut-caption">orders</div>
                </div>
              </div>
              <div className="donut-legend">
                {orderTypeData.map(item => (
                  <div key={item.name} className="legend-item">
                    <span className="legend-color" style={{ backgroundColor: item.color }} />
                    <span className="legend-label">{item.name}</span>
                    <span className="legend-count">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Row */}
      <div className="bottom-row">
        {/* Top Products */}
        <div className="chart-panel">
          <h3 className="panel-title">Top Products</h3>
          {data.top_products.length === 0 ? (
            <div className="empty-state">No sales</div>
          ) : (
            <ResponsiveContainer width="100%" height={170}>
              <BarChart
                data={topProductsData}
                layout="vertical"
                margin={{ top: 0, right: 30, left: 160, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#2c2f38" horizontal={false} />
                <XAxis type="number" stroke="#8b8fa3" style={{ fontSize: "11px" }} tick={{ fill: "#8b8fa3" }} allowDecimals={false} />
                <YAxis
                  dataKey="name"
                  type="category"
                  stroke="#8b8fa3"
                  style={{ fontSize: "11px" }}
                  tick={{ fill: "#8b8fa3" }}
                  width={150}
                />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1c1f27", border: "1px solid #2c2f38", borderRadius: "6px" }}
                  labelStyle={{ color: "#f2f3f7" }}
                />
                <Bar dataKey="qty" fill="#F5B301" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* By Staff Table */}
        <div className="chart-panel">
          <h3 className="panel-title">By Staff</h3>
          {data.per_staff.length === 0 ? (
            <div className="empty-state">No staff activity</div>
          ) : (
            <div className="staff-table-compact">
              <div className="staff-header">
                <span className="staff-col name">Name</span>
                <span className="staff-col">Sales</span>
                <span className="staff-col">Orders</span>
                <span className="staff-col">Cancelled</span>
              </div>
              {data.per_staff.map((staff) => (
                <div key={staff.user_id ?? "unknown"} className="staff-row">
                  <span className="staff-col name">{staff.user_name || "Before staff tracking"}</span>
                  <span className="staff-col">{formatCurrency(staff.sales)}</span>
                  <span className="staff-col">{staff.orders}</span>
                  <span className={`staff-col ${staff.cancelled > 0 ? "danger" : ""}`}>{staff.cancelled}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
