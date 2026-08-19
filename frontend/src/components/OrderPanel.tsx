import { useState, useMemo, useContext } from "react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { Minus, Plus, Trash2 } from "lucide-react";
import { usePOS } from "../context/POSContext";
import { SettingsContext } from "../context/SettingsContext";
import { rupeesToPaisa, paisaToRupees } from "../utils/money";
import { CustomerPanel } from "./CustomerPanel";

export function OrderPanel({ onPay }: { onPay: () => void }) {
  const formatCurrency = useCurrencyFormat();
  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;
  const {
    state,
    subtotal,
    discount,
    tax,
    deliveryCharge,
    total,
    setQty,
    removeProduct,
    setDiscount,
  } = usePOS();

  const [discountText, setDiscountText] = useState(
    String(paisaToRupees(state.discount))
  );

  return (
    <aside className="order-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">CURRENT ORDER</p>
          <h2>Order</h2>
        </div>

        <span>
          {state.cart.reduce((s, i) => s + i.quantity, 0)} items
        </span>
      </div>

      <div className="order-items">
        {!state.cart.length ? (
          <div className="empty-cart">
            <div className="empty-icon">+</div>
            <strong>Your order is empty</strong>
            <span>Select items from the menu.</span>
          </div>
        ) : (
          state.cart.map((i) => {
            const productId=i.kind==="local"?i.product.id:i.productId;
            const productName=i.kind==="local"?i.product.name_display:i.productName;
            const productPrice=i.kind==="local"?i.product.price:i.price;
            const rowKey=i.kind==="local"?`local-${i.product.id}`:`server-${i.itemId}`;
            const isLocal=i.kind==="local";
            const atStockLimit=isLocal&&i.quantity>=i.product.stock;

            return (
              <div className="cart-row" key={rowKey}>
                <div className="cart-main">
                  <strong>{productName}</strong>

                  <span>
                    {formatCurrency(productPrice)} each
                  </span>

                  {isLocal&&atStockLimit && (
                    <span className="cart-stock-hint">
                      Only {i.product.stock} in stock
                    </span>
                  )}
                </div>

                <div className="cart-actions">
                  <button
                    onClick={() =>
                      setQty(productId, i.quantity - 1)
                    }
                  >
                    <Minus size={14} />
                  </button>

                  <b>{i.quantity}</b>

                  <button
                    disabled={atStockLimit}
                    onClick={() =>
                      setQty(productId, i.quantity + 1)
                    }
                  >
                    <Plus size={14} />
                  </button>

                  <button
                    onClick={() => removeProduct(productId)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>

                <strong className="line-total">
                  {formatCurrency(productPrice * i.quantity)}
                </strong>
              </div>
            );
          })
        )}
      </div>

      <div className="order-summary">
        <CustomerPanel />

        <div className="field-grid">
          <label>
            Discount

            <input
              type="number"
              min="0"
              value={discountText}
              onChange={(e) => {
                setDiscountText(e.target.value);
                setDiscount(rupeesToPaisa(parseFloat(e.target.value) || 0));
              }}
            />
          </label>
        </div>

        <div className="summary-row">
          <span>Subtotal</span>
          <b>{formatCurrency(subtotal)}</b>
        </div>

        <div className="summary-row">
          <span>Discount</span>
          <b>- {formatCurrency(discount)}</b>
        </div>

        {settings?.tax_enabled && (
          <div className="summary-row">
            <span>Tax</span>
            <b>{formatCurrency(tax)}</b>
          </div>
        )}

        {deliveryCharge > 0 && (
          <div className="summary-row">
            <span>Delivery</span>
            <b>{formatCurrency(deliveryCharge)}</b>
          </div>
        )}

        <div className="total-row">
          <span>Total</span>
          <strong>{formatCurrency(total)}</strong>
        </div>

        <button
          className="pay-button"
          disabled={!state.cart.length}
          onClick={onPay}
        >
          Proceed to Payment
        </button>
      </div>
    </aside>
  );
}