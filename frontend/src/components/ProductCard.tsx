import { useState } from "react";
import type { Product } from "../types";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { API_URL } from "../services/api";

export function ProductCard({
  product,
  onAdd,
  isDisabled,
}: {
  product: Product;
  onAdd: (p: Product) => void;
  isDisabled?: boolean;
}) {
  const formatCurrency = useCurrencyFormat();
  const [imageError, setImageError] = useState(false);
  const isDeal = product.product_type === "DEAL";

  // For deals, never check stock_status — deals are always tappable.
  // For regular products, use the backend's authoritative stock_status (Phase 3).
  const outOfStock = !isDeal && product.stock_status === "OUT_OF_STOCK";
  const hasSizes = product.sizes && product.sizes.length > 0;
  const showImage = product.image && !imageError;

  // For deals, format component names with sizes: "Name1 + Name2 (Large) + ..."
  const componentNames = isDeal && product.components.length > 0
    ? product.components.map(c => c.size_name ? `${c.product_name} (${c.size_name})` : c.product_name).join(" + ")
    : null;

  return (
    <button
      className={outOfStock ? "product-card out-of-stock" : "product-card"}
      onClick={() => !outOfStock && onAdd(product)}
      disabled={outOfStock || isDisabled}
      title={componentNames ? componentNames : undefined}
    >
      <div className="product-thumb">
        {showImage ? (
          <img
            src={`${API_URL}/images/${product.image}?v=${product.image_hash}`}
            alt={product.name_display}
            onError={() => setImageError(true)}
          />
        ) : (
          product.name_display[0]
        )}
      </div>

      <div className="product-info">
        <strong>{product.name_display}</strong>
        {outOfStock ? (
          <span className="status-badge out-of-stock">Out of Stock</span>
        ) : isDeal ? (
          <>
            <span className="status-badge deal-badge">DEAL</span>
            <span className="deal-components">{componentNames}</span>
          </>
        ) : hasSizes ? (
          <span className="status-badge size-options">Choose Size</span>
        ) : (
          <>
            <span>{formatCurrency(product.price)}</span>
            <span>Stock: {product.stock}</span>
          </>
        )}
      </div>
    </button>
  );
}
