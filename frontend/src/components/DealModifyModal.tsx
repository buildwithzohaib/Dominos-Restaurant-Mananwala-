import { useState, useMemo } from "react";
import { X, Trash2, ChevronDown } from "lucide-react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import type { Product, DealModificationComponent, DealModifications, DealComponentOut } from "../types";

// Swap selection modal component
function SwapProductModal({
  catalogProducts,
  originalComponent,
  onSelect,
  onCancel,
}: {
  catalogProducts: Product[];
  originalComponent: DealComponentOut;
  onSelect: (product: Product, sizeId?: number) => void;
  onCancel: () => void;
}) {
  const [searchText, setSearchText] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedSize, setSelectedSize] = useState<number | null>(null);

  // Filter to ordinary products only (not deals)
  const filteredProducts = useMemo(() => {
    const ordinary = catalogProducts.filter(p => p.product_type !== "DEAL");
    if (!searchText.trim()) {
      return ordinary;
    }
    const lower = searchText.toLowerCase();
    return ordinary.filter(p => p.name_display.toLowerCase().includes(lower));
  }, [catalogProducts, searchText]);

  const handleSelectProduct = (product: Product) => {
    setSelectedProduct(product);
    setSelectedSize(null); // Reset size selection when product changes
  };

  const handleConfirm = () => {
    if (!selectedProduct) return;
    if (selectedProduct.sizes.length > 0 && !selectedSize) {
      return; // Size required
    }
    onSelect(selectedProduct, selectedSize || undefined);
  };

  const isValid = selectedProduct && (selectedProduct.sizes.length === 0 || selectedSize);

  return (
    <div className="modal-backdrop">
      <div className="inventory-modal">
        <button className="modal-close" onClick={onCancel}>
          <X />
        </button>

        <p className="eyebrow">SWAP COMPONENT</p>
        <h2>Replace {originalComponent.product_name}</h2>

        <div className="deal-modify-section">
          <label className="deal-modify-label">Search for replacement:</label>
          <input
            type="text"
            autoFocus
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Type product name..."
            className="deal-modify-input"
          />
        </div>

        <div className="deal-modify-section">
          <h4 className="deal-modify-heading">Available Products</h4>
          <div className="product-swap-list">
            {filteredProducts.length === 0 ? (
              <div className="swap-no-results">No products found</div>
            ) : (
              filteredProducts.map(product => (
                <button
                  key={product.id}
                  onClick={() => handleSelectProduct(product)}
                  className={`swap-product-item ${selectedProduct?.id === product.id ? "selected" : ""}`}
                >
                  <div className="swap-product-name">{product.name_display}</div>
                  <div className="swap-product-price">Rs. {(product.price / 100).toFixed(2)}</div>
                </button>
              ))
            )}
          </div>
        </div>

        {selectedProduct && selectedProduct.sizes.length > 0 && (
          <div className="deal-modify-section">
            <label className="deal-modify-label">Size required:</label>
            <select
              value={selectedSize || ""}
              onChange={(e) => setSelectedSize(parseInt(e.target.value) || null)}
              className="deal-modify-input"
            >
              <option value="">Choose a size</option>
              {selectedProduct.sizes.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name} — Rs. {(s.price / 100).toFixed(2)}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="deal-modify-actions">
          <button className="secondary-button" onClick={onCancel}>
            Cancel
          </button>
          <button className="pay-button" onClick={handleConfirm} disabled={!isValid}>
            Confirm Swap
          </button>
        </div>
      </div>
    </div>
  );
}

export function DealModifyModal({
  deal,
  catalogProducts,
  onClose,
  onAccept,
}: {
  deal: Product;
  catalogProducts: Product[];
  onClose: () => void;
  onAccept: (modifications: DealModifications) => void;
}) {
  const formatCurrency = useCurrencyFormat();
  const [components, setComponents] = useState<DealModificationComponent[]>(
    deal.components.map(c => ({
      product_id: c.product_id,
      quantity: c.quantity,
      size_id: c.size_id,
      was_removed: false,
    }))
  );
  const [priceOverride, setPriceOverride] = useState<string>("");
  const [error, setError] = useState("");
  const [swapIndex, setSwapIndex] = useState<number | null>(null);

  // Calculate price changes, total, and validation
  const priceCalculation = useMemo(() => {
    const changes: { label: string; amount: number }[] = [];
    let total = deal.price;
    const active = components.filter(c => !c.was_removed);

    for (let i = 0; i < components.length; i++) {
      const comp = components[i];
      const original = deal.components[i];
      if (!original) continue;

      if (comp.was_removed) {
        // Removing: subtract full component price
        const removed = original.component_price;
        changes.push({
          label: `- Remove ${original.product_name}`,
          amount: -removed,
        });
        total -= removed;
      } else if (comp.product_id_original) {
        // Component was swapped: subtract original price, add replacement price
        const replacedFromPrice = original.component_price;
        const replacedToProduct = catalogProducts.find(p => p.id === comp.product_id);
        let replacedToPrice = 0;

        if (replacedToProduct) {
          if (comp.size_id) {
            const size = replacedToProduct.sizes.find(s => s.id === comp.size_id);
            replacedToPrice = size ? size.price : replacedToProduct.price;
          } else {
            replacedToPrice = replacedToProduct.price;
          }
        }

        const difference = replacedToPrice - replacedFromPrice;
        changes.push({
          label: `${original.product_name} → ${replacedToProduct?.name_display || "Unknown"}`,
          amount: difference,
        });
        total += difference;
      } else if (comp.size_id !== original.size_id && comp.size_id) {
        // Size changed: calculate difference
        const compProduct = catalogProducts.find(p => p.id === comp.product_id);
        const oldSize = original.size_id
          ? compProduct?.sizes.find(s => s.id === original.size_id)
          : null;
        const newSize = compProduct?.sizes.find(s => s.id === comp.size_id);

        if (oldSize && newSize) {
          const difference = newSize.price - oldSize.price;
          const oldSizeName = oldSize.name;
          const newSizeName = newSize.name;
          changes.push({
            label: `${original.product_name}: ${oldSizeName} → ${newSizeName}`,
            amount: difference,
          });
          total += difference;
        }
      }
    }

    return { changes, total, activeCount: active.length };
  }, [components, deal, catalogProducts]);

  const finalPrice = priceOverride
    ? Math.floor(parseFloat(priceOverride) * 100 || 0)
    : priceCalculation.total;

  const handleRemove = (idx: number) => {
    setComponents(c => {
      const updated = [...c];
      updated[idx].was_removed = !updated[idx].was_removed;
      return updated;
    });
  };

  const handleSizeChange = (idx: number, sizeId: number) => {
    setComponents(c => {
      const updated = [...c];
      updated[idx].size_id = sizeId;
      return updated;
    });
  };

  const handleSwapClick = (idx: number) => {
    setSwapIndex(idx);
  };

  const handleSwapProduct = (replacement: Product, sizeId?: number) => {
    if (swapIndex === null) return;

    setComponents(c => {
      const updated = [...c];
      const original = deal.components[swapIndex];
      if (original) {
        updated[swapIndex] = {
          ...updated[swapIndex],
          product_id: replacement.id,
          product_id_original: original.product_id,
          size_id: sizeId || (replacement.sizes.length === 0 ? null : undefined),
        };
      }
      return updated;
    });
    setSwapIndex(null);
  };

  const handleUndoSwap = (idx: number) => {
    setComponents(c => {
      const updated = [...c];
      const original = deal.components[idx];
      if (original && updated[idx].product_id_original) {
        updated[idx] = {
          product_id: original.product_id,
          quantity: original.quantity,
          size_id: original.size_id,
          was_removed: false,
        };
      }
      return updated;
    });
  };

  // Show error immediately if all components removed
  const validationError = priceCalculation.activeCount === 0
    ? "Deal cannot have all components removed."
    : "";

  const handleAccept = () => {
    if (validationError) {
      return;
    }
    onAccept({
      components,
      price: finalPrice,
      standard_price: deal.price,
    });
  };

  if (swapIndex !== null) {
    return (
      <SwapProductModal
        catalogProducts={catalogProducts}
        originalComponent={deal.components[swapIndex]}
        onSelect={handleSwapProduct}
        onCancel={() => setSwapIndex(null)}
      />
    );
  }

  return (
    <div className="modal-backdrop">
      <div className="inventory-modal deal-modify-modal">
        <button className="modal-close" onClick={onClose}>
          <X />
        </button>

        <p className="eyebrow">MODIFY DEAL</p>
        <h2>{deal.name_display}</h2>

        {(error || validationError) && <div className="error-box deal-modify-error">{error || validationError}</div>}

        <div className="deal-modify-section">
          <h4 className="deal-modify-heading">Components</h4>
          <div className="deal-modify-components">
            {deal.components.map((comp, idx) => {
              const comp_mod = components[idx];
              const isRemoved = comp_mod.was_removed;
              const isSwapped = !!comp_mod.product_id_original;
              const displayProduct = catalogProducts.find(p => p.id === comp_mod.product_id);
              const hasSizes = displayProduct && displayProduct.sizes && displayProduct.sizes.length > 0;

              return (
                <div
                  key={idx}
                  className={`deal-modify-component ${isRemoved ? "removed" : ""} ${isSwapped ? "swapped" : ""}`}
                >
                  <div className="deal-modify-component-info">
                    <strong>{displayProduct?.name_display || comp.product_name}</strong>
                    {hasSizes && !isRemoved ? (
                      <select
                        value={comp_mod.size_id || ""}
                        onChange={(e) => handleSizeChange(idx, parseInt(e.target.value) || 0)}
                        className="deal-modify-size-select"
                      >
                        {displayProduct?.sizes.map(s => (
                          <option key={s.id} value={s.id}>
                            {s.name}
                          </option>
                        ))}
                      </select>
                    ) : !isSwapped && comp.size_name && !isRemoved ? (
                      <span className="component-size">({comp.size_name})</span>
                    ) : null}
                  </div>
                  <div className="deal-modify-component-actions">
                    {isSwapped && (
                      <button
                        className="row-action-button"
                        onClick={() => handleUndoSwap(idx)}
                        title="Undo swap"
                      >
                        ↶
                      </button>
                    )}
                    {!isRemoved && (
                      <button
                        className="row-action-button"
                        onClick={() => handleSwapClick(idx)}
                        title="Swap for different product"
                      >
                        ⇄
                      </button>
                    )}
                    <button
                      className="row-action-button"
                      onClick={() => handleRemove(idx)}
                      title={isRemoved ? "Restore" : "Remove"}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="deal-modify-section">
          <h4 className="deal-modify-heading">Price</h4>
          <div className="deal-modify-breakdown">
            <div className="deal-modify-price-line">
              <span>Base price:</span>
              <strong>{formatCurrency(deal.price)}</strong>
            </div>
            {priceCalculation.changes.map((change, idx) => (
              <div key={idx} className={`deal-modify-price-line ${change.amount < 0 ? "negative" : ""}`}>
                <span>{change.label}:</span>
                <span>{formatCurrency(change.amount)}</span>
              </div>
            ))}
            {priceCalculation.changes.length > 0 && (
              <div className="deal-modify-price-line calculated">
                <span>Calculated:</span>
                <strong>{formatCurrency(priceCalculation.total)}</strong>
              </div>
            )}
          </div>

          <div className="deal-modify-price-input">
            <label className="deal-modify-label">Final Price</label>
            <input
              type="text"
              value={priceOverride || (finalPrice / 100).toFixed(2)}
              onChange={(e) => setPriceOverride(e.target.value)}
              placeholder={(finalPrice / 100).toFixed(2)}
              className="deal-modify-input"
            />
          </div>
        </div>

        <div className="deal-modify-actions">
          <button className="secondary-button" onClick={onClose}>
            Cancel
          </button>
          <button className="pay-button" onClick={handleAccept} disabled={!!validationError}>
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
