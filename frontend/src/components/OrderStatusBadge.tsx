import type { OrderStatus } from "../types";

const LABELS: Record<OrderStatus, string> = {
  PAID: "Paid",
  CANCELLED: "Cancelled",
};

const CLASSES: Record<OrderStatus, string> = {
  PAID: "in-stock",
  CANCELLED: "out-of-stock",
};

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={`status-badge ${CLASSES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
