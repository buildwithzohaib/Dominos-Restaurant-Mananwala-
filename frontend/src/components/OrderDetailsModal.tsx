import { X } from "lucide-react";
import { useContext } from "react";

import { OrderStatusBadge } from "./OrderStatusBadge";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { SettingsContext } from "../context/SettingsContext";
import { parseServerDate } from "../utils/dates";
import type { Order } from "../types";

export function OrderDetailsModal({
  order,
  onClose,
  onCancelRequested,
}: {
  order: Order;
  onClose: () => void;
  onCancelRequested: () => void;
}) {
  const formatCurrency = useCurrencyFormat();
  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;
  return (
    <div className="modal-backdrop">
      <div className="inventory-modal order-details-modal">
        <button className="modal-close" onClick={onClose}>
          <X />
        </button>

        <p className="eyebrow">ORDERS</p>
        <h2>Order {order.order_number}</h2>

        <div className="order-meta-row">
          <span>{order.order_type.replace("_", " ")}</span>
          <span>{parseServerDate(order.created_at).toLocaleString()}</span>
        </div>

        <div className="receipt-line" />

        {/* Customer info */}
        <div className="order-status-row">
          <div>
            <span>Customer</span>
            <strong>
              {order.customer
                ? `${order.customer.name_display}${order.customer.phone_raw ? ` • ${order.customer.phone_raw}` : ""}`
                : "Walk-in"}
            </strong>
          </div>
        </div>

        {/* Delivery address */}
        {order.delivery_address && (
          <div className="order-meta-row">
            <span>Delivery Address</span>
            <span>{order.delivery_address}</span>
          </div>
        )}

        <div className="receipt-line" />

        <div className="receipt-items">
          {order.items.map((item) => (
            <div className="receipt-item" key={item.id}>
              <div>
                <strong>{item.product_name}</strong>
                <span>
                  {item.quantity} × {formatCurrency(item.price)}
                </span>
              </div>
              <strong>{formatCurrency(item.line_total)}</strong>
            </div>
          ))}
        </div>

        <div className="receipt-line" />

        <div className="receipt-summary">
          <div>
            <span>Subtotal</span>
            <strong>{formatCurrency(order.subtotal)}</strong>
          </div>
          <div>
            <span>Discount</span>
            <strong>- {formatCurrency(order.discount)}</strong>
          </div>
          {settings?.tax_enabled && (
            <div>
              <span>Tax</span>
              <strong>{formatCurrency(order.tax)}</strong>
            </div>
          )}
          {order.delivery_charge && order.delivery_charge > 0 && (
            <div>
              <span>Delivery</span>
              <strong>{formatCurrency(order.delivery_charge)}</strong>
            </div>
          )}
          <div className="receipt-grand-total">
            <span>TOTAL</span>
            <strong>{formatCurrency(order.total)}</strong>
          </div>
        </div>

        <div className="receipt-line" />

        <div className="order-status-row">
          <div>
            <span>Payment</span>
            <strong>{order.payment_method}</strong>
          </div>
          <div>
            <span>Status</span>
            <OrderStatusBadge status={order.status} />
          </div>
        </div>

        {order.status === "CANCELLED" && (
          <div className="cancelled-info-box">
            <strong>Cancelled</strong>
            <span>{order.cancelled_reason}</span>
            {order.cancelled_at && (
              <span>{parseServerDate(order.cancelled_at).toLocaleString()}</span>
            )}
          </div>
        )}

        {order.status === "PAID" && (
          <button className="pay-button danger" onClick={onCancelRequested}>
            Cancel Order
          </button>
        )}
      </div>
    </div>
  );
}
