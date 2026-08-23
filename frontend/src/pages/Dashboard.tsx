import { useEffect, useState } from "react";
import { LineChart, Line, AreaChart, Area, PieChart, Pie, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from "recharts";
import { X } from "lucide-react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { api } from "../services/api";
import type { DashboardRange, Order } from "../types";
import { parseServerDate } from "../utils/dates";

// Get CSS token colors at runtime for recharts
function getCSSToken(tokenName: string): string {
  const css = getComputedStyle(document.documentElement);
  return css.getPropertyValue(tokenName).trim();
}

type RangeType = "today" | "7days" | "30days";
type MetricType = "sales" | "orders" | "cancelled" | "discounts" | "staff";

interface MetricModal {
  metric: MetricType;
  range: RangeType;
  userId?: number | null;
  noUser?: boolean;
  title: string;
}

export function Dashboard({ onLowStockClick }: { onLowStockClick?: () => void }) {
  const formatCurrency = useCurrencyFormat();
  const [range, setRange] = useState<RangeType>("today");
  const [data, setData] = useState<DashboardRange | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Read CSS tokens for chart colors
  const colors = {
    dashSurface: getCSSToken("--dash-surface"),
    dashLine: getCSSToken("--dash-line"),
    dashText: getCSSToken("--dash-text"),
    dashTextMuted: getCSSToken("--dash-text-muted"),
    dashAccent: getCSSToken("--dash-accent"),
    chart1: getCSSToken("--chart-1"),
    chart2: getCSSToken("--chart-2"),
    chart3: getCSSToken("--chart-3"),
  };

  const [metricModal, setMetricModal] = useState<MetricModal | null>(null);
  const [metricOrders, setMetricOrders] = useState<Order[]>([]);
  const [metricLoading, setMetricLoading] = useState(false);
  const [metricError, setMetricError] = useState("");

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

  const openMetricModal = async (metric: MetricType, range: RangeType, title: string, userId?: number | null, noUser?: boolean) => {
    setMetricModal({ metric, range, userId, noUser, title });
    setMetricLoading(true);
    setMetricError("");

    try {
      const orders = await api.getDashboardOrders(metric, range, userId, noUser);
      setMetricOrders(orders);
    } catch (e) {
      setMetricError(e instanceof Error ? e.message : "Could not load orders");
    } finally {
      setMetricLoading(false);
    }
  };

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
    { name: "Dine-in", value: data.dine_in_count, color: colors.chart1 },
    { name: "Takeaway", value: data.takeaway_count, color: colors.chart2 },
    { name: "Delivery", value: data.delivery_count, color: colors.chart3 }
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
        {/* Sales - Clickable */}
        <div className="kpi-tile clickable" onClick={() => openMetricModal("orders", range, `Orders — ${range === "today" ? "today" : range === "7days" ? "last 7 days" : "last 30 days"}`)}>
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

        {/* Orders - Clickable */}
        <div className="kpi-tile clickable" onClick={() => openMetricModal("orders", range, `Orders — ${range === "today" ? "today" : range === "7days" ? "last 7 days" : "last 30 days"}`)}>
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

        {/* Discounts - Clickable */}
        <div className="kpi-tile bordered-amber clickable" onClick={() => openMetricModal("discounts", range, `Discounts — ${range === "today" ? "today" : range === "7days" ? "last 7 days" : "last 30 days"}`)}>
          <p className="kpi-label">Discounts</p>
          <p className="kpi-value">{formatCurrency(data.discount_total)}</p>
          <p className="kpi-context">{data.discount_order_count} orders</p>
        </div>

        {/* Cancelled - Clickable */}
        <div className="kpi-tile bordered-red clickable" onClick={() => openMetricModal("cancelled", range, `Cancelled orders — ${range === "today" ? "today" : range === "7days" ? "last 7 days" : "last 30 days"}`)}>
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

        {/* Low Stock - Navigates to Inventory */}
        <div className="kpi-tile bordered-amber clickable" onClick={onLowStockClick}>
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
            <div className="chart-wrapper">
              <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailySalesData} margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={colors.dashAccent} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={colors.dashAccent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.dashLine} vertical={false} />
                <XAxis
                  dataKey="date"
                  stroke={colors.dashTextMuted}
                  style={{ fontSize: "11px" }}
                  tick={{ fill: colors.dashTextMuted }}
                  interval={Math.max(0, Math.floor(dailySalesData.length / 6))}
                />
                <YAxis
                  stroke={colors.dashTextMuted}
                  style={{ fontSize: "11px" }}
                  tick={{ fill: colors.dashTextMuted }}
                />
                <Tooltip
                  contentStyle={{ backgroundColor: colors.dashSurface, border: `1px solid ${colors.dashLine}`, borderRadius: "6px" }}
                  labelStyle={{ color: colors.dashText }}
                />
                <Area
                  type="linear"
                  dataKey="revenue"
                  stroke={colors.dashAccent}
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorRevenue)"
                  dot={false}
                  activeDot={{ fill: colors.dashAccent, r: 4 }}
                />
              </AreaChart>
            </ResponsiveContainer>
            </div>
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
                <ResponsiveContainer width="100%" height="100%">
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
                      contentStyle={{ backgroundColor: colors.dashSurface, border: `1px solid ${colors.dashLine}`, borderRadius: "6px" }}
                      labelStyle={{ color: colors.dashText }}
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
            <div className="chart-wrapper">
              <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={topProductsData}
                layout="vertical"
                margin={{ top: 0, right: 30, left: 160, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={colors.dashLine} horizontal={false} />
                <XAxis type="number" stroke={colors.dashTextMuted} style={{ fontSize: "11px" }} tick={{ fill: colors.dashTextMuted }} allowDecimals={false} />
                <YAxis
                  dataKey="name"
                  type="category"
                  stroke={colors.dashTextMuted}
                  style={{ fontSize: "11px" }}
                  tick={{ fill: colors.dashTextMuted }}
                  width={150}
                />
                <Tooltip
                  contentStyle={{ backgroundColor: colors.dashSurface, border: `1px solid ${colors.dashLine}`, borderRadius: "6px" }}
                  labelStyle={{ color: colors.dashText }}
                />
                <Bar dataKey="qty" fill={colors.dashAccent} />
              </BarChart>
            </ResponsiveContainer>
            </div>
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
                <div
                  key={staff.user_id ?? "unknown"}
                  className="staff-row clickable"
                  onClick={() => {
                    const title = staff.user_name
                      ? `Orders by ${staff.user_name} — ${range === "today" ? "today" : range === "7days" ? "last 7 days" : "last 30 days"}`
                      : `Orders before staff tracking — ${range === "today" ? "today" : range === "7days" ? "last 7 days" : "last 30 days"}`;
                    if (staff.user_id === null) {
                      openMetricModal("staff", range, title, null, true);
                    } else {
                      openMetricModal("staff", range, title, staff.user_id);
                    }
                  }}
                >
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

      {/* Metric Orders Modal */}
      {metricModal && (
        <div className="modal-backdrop" onClick={() => setMetricModal(null)}>
          <div className="dashboard-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setMetricModal(null)}>
              <X size={20} />
            </button>

            <h2 className="modal-title">{metricModal.title}</h2>
            <p className="modal-count">{metricOrders.length} {metricOrders.length === 1 ? "order" : "orders"}</p>

            {metricLoading && <div className="modal-loading">Loading orders...</div>}

            {metricError && <div className="modal-error">{metricError}</div>}

            {!metricLoading && metricOrders.length === 0 && (
              <div className="modal-empty">No orders found</div>
            )}

            {!metricLoading && metricOrders.length > 0 && (
              <div className="modal-orders-list">
                {metricOrders.map((order) => (
                  <div key={order.id} className="modal-order-row">
                    <div className="modal-order-header">
                      <strong className="modal-order-number">#{order.order_number}</strong>
                      <span className="modal-order-type">{order.order_type.replace("_", " ")}</span>
                      <span className="modal-order-time">{parseServerDate(metricModal.metric === "cancelled" ? order.cancelled_at || order.created_at : order.paid_at || order.created_at).toLocaleTimeString()}</span>
                    </div>
                    <div className="modal-order-details">
                      <span>{order.customer ? order.customer.name_display : "Walk-in"}</span>
                      {order.performed_by && <span className="modal-order-staff">{order.performed_by.name}</span>}
                      {metricModal.metric === "cancelled" && order.cancelled_reason && (
                        <span className="modal-order-reason">{order.cancelled_reason}</span>
                      )}
                    </div>
                    <div className="modal-order-total">{formatCurrency(order.total)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
