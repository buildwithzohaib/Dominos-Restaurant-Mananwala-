import type { StockStatus } from "../types";

const LABELS: Record<StockStatus, string> = {
  IN_STOCK: "In Stock",
  LOW_STOCK: "Low Stock",
  OUT_OF_STOCK: "Out of Stock",
};

const CLASSES: Record<StockStatus, string> = {
  IN_STOCK: "in-stock",
  LOW_STOCK: "low-stock",
  OUT_OF_STOCK: "out-of-stock",
};

export function StatusBadge({ status }: { status: StockStatus }) {
  return (
    <span className={`status-badge ${CLASSES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
