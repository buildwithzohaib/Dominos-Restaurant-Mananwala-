import { useState } from "react";
import type { Product } from "../types";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { API_URL } from "../services/api";

export function ProductCard({
  product,
  onAdd,
}: {
  product: Product;
  onAdd: (p: Product) => void;
}) {
  const formatCurrency = useCurrencyFormat();
  const [imageError, setImageError] = useState(false);
  // Reuse the backend's authoritative stock_status (Phase 3) rather than
  // re-deriving availability from stock/available locally — one status
  // calculation, computed on the server, read everywhere.
  const outOfStock = product.stock_status === "OUT_OF_STOCK";
  const showImage = product.image && !imageError;

  return (
    <button
      className={outOfStock ? "product-card out-of-stock" : "product-card"}
      onClick={() => !outOfStock && onAdd(product)}
      disabled={outOfStock}
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
