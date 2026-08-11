import { X } from "lucide-react";

import { OrderStatusBadge } from "./OrderStatusBadge";
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
          <span>{new Date(order.created_at).toLocaleString()}</span>
        </div>

        <div className="receipt-line" />

        <div className="receipt-items">
          {order.items.map((item) => (
            <div className="receipt-item" key={item.id}>
              <div>
                <strong>{item.product_name}</strong>
                <span>
                  {item.quantity} × Rs. {Number(item.price).toFixed(2)}
                </span>
              </div>
              <strong>Rs. {Number(item.line_total).toFixed(2)}</strong>
            </div>
          ))}
        </div>

        <div className="receipt-line" />

        <div className="receipt-summary">
          <div>
            <span>Subtotal</span>
            <strong>Rs. {Number(order.subtotal).toFixed(2)}</strong>
          </div>
          <div>
            <span>Discount</span>
            <strong>- Rs. {Number(order.discount).toFixed(2)}</strong>
          </div>
          <div>
            <span>Tax</span>
            <strong>Rs. {Number(order.tax).toFixed(2)}</strong>
          </div>
          <div className="receipt-grand-total">
            <span>TOTAL</span>
            <strong>Rs. {Number(order.total).toFixed(2)}</strong>
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
              <span>{new Date(order.cancelled_at).toLocaleString()}</span>
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
