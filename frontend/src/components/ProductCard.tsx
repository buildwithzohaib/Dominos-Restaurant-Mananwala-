import type { Product } from "../types";

export function ProductCard({
  product,
  onAdd,
}: {
  product: Product;
  onAdd: (p: Product) => void;
}) {
  // Reuse the backend's authoritative stock_status (Phase 3) rather than
  // re-deriving availability from stock/available locally — one status
  // calculation, computed on the server, read everywhere.
  const outOfStock = product.stock_status === "OUT_OF_STOCK";

  return (
    <button
      className={outOfStock ? "product-card out-of-stock" : "product-card"}
      onClick={() => !outOfStock && onAdd(product)}
      disabled={outOfStock}
    >
      <div className="product-thumb">
        {product.name[0]}
      </div>

      <div className="product-info">
        <strong>{product.name}</strong>
        {outOfStock ? (
          <span className="status-badge out-of-stock">Out of Stock</span>
        ) : (
          <>
            <span>Rs. {Number(product.price).toFixed(2)}</span>
            <span>Stock: {product.stock}</span>
          </>
        )}
      </div>
    </button>
  );
}
