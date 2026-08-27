import { X } from "lucide-react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import type { Product, ProductSize } from "../types";

export function SizeSelectModal({
  product,
  onClose,
  onSelect,
}: {
  product: Product;
  onClose: () => void;
  onSelect: (size: ProductSize) => void;
}) {
  const formatCurrency = useCurrencyFormat();
  const sizes = product.sizes || [];

  // Sort sizes by sort_order
  const sorted = [...sizes].sort((a, b) => a.sort_order - b.sort_order);

  return (
    <div className="modal-backdrop">
      <div className="inventory-modal" style={{ maxWidth: "400px" }}>
        <button className="modal-close" onClick={onClose}>
          <X />
        </button>

        <p className="eyebrow">SELECT SIZE</p>
        <h2>{product.name_display}</h2>

        <div style={{ marginTop: "20px", display: "flex", flexDirection: "column", gap: "8px" }}>
          {sorted.map((size) => (
            <button
              key={size.id}
              className="size-option-button"
              onClick={() => onSelect(size)}
            >
              <span>{size.name}</span>
              <strong>{formatCurrency(size.price)}</strong>
            </button>
          ))}
        </div>

        <div style={{ marginTop: "20px" }}>
          <button className="secondary-button" onClick={onClose} style={{ width: "100%" }}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
