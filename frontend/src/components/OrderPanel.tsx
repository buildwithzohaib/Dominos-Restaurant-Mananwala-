import { useState, useMemo, useContext } from "react";
import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { Minus, Plus, Trash2 } from "lucide-react";
import { usePOS } from "../context/POSContext";
import { SettingsContext } from "../context/SettingsContext";
import { rupeesToPaisa, paisaToRupees } from "../utils/money";
import { CustomerPanel } from "./CustomerPanel";
import { CancelOrderModal } from "./CancelOrderModal";
import { api } from "../services/api";
import type { Order } from "../types";

export function OrderPanel({ onPay, onCancelSuccess }: { onPay: () => void; onCancelSuccess?: () => void }) {
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
    setQtyOnServerItem,
    removeServerItem,
    clear,
    sendBatchAndLoad,
  } = usePOS();

  const [error, setError] = useState("");
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [sendBusy, setSendBusy] = useState(false);

  const [discountText, setDiscountText] = useState(
    String(paisaToRupees(state.discount))
  );

  const handleSendToKitchen = async () => {
    if (!state.serverId) return;
    setSendBusy(true);
    setError("");
    try {
      await sendBatchAndLoad(state.serverId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send to kitchen");
    } finally {
      setSendBusy(false);
    }
  };

  const handleCancelSuccess = () => {
    setCancelModalOpen(false);
    clear();
    onCancelSuccess?.();
  };

  const hasPendingItems = state.cart.some(i => i.kind === "server" && i.batchId === null);
  const canSend = state.serverId && hasPendingItems;
  const canPay = state.cart.length > 0 && !state.cart.some(i => i.kind === "server" && i.batchId === null);

  return (
    <>
    <aside className="order-panel">
      {error && (
        <div className="error-box">
          {error}
        </div>
      )}
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

            const isSent = i.kind === "server" && i.batchId !== null;

            return (
              <div className={`cart-row ${isSent ? "cart-row-sent" : ""}`} key={rowKey}>
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
                    disabled={isSent}
                    onClick={async () => {
                      try {
                        if (i.kind === "local") {
                          setQty(productId, i.quantity - 1);
                        } else {
                          await setQtyOnServerItem(state.serverId!, i.itemId, i.quantity - 1);
                        }
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Failed to update quantity");
                      }
                    }}
                  >
                    <Minus size={14} />
                  </button>

                  <b>{i.quantity}</b>

                  <button
                    disabled={atStockLimit || isSent}
                    onClick={async () => {
                      try {
                        if (i.kind === "local") {
                          setQty(productId, i.quantity + 1);
                        } else {
                          await setQtyOnServerItem(state.serverId!, i.itemId, i.quantity + 1);
                        }
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Failed to update quantity");
                      }
                    }}
                  >
                    <Plus size={14} />
                  </button>

                  <button
                    disabled={isSent}
                    onClick={async () => {
                      try {
                        if (i.kind === "local") {
                          removeProduct(productId);
                        } else {
                          await removeServerItem(state.serverId!, i.itemId);
                        }
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Failed to remove item");
                      }
                    }}
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

        {state.orderType !== "DINE_IN" && (
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
        )}

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

        {state.serverId ? (
          <>
            <button
              className="secondary-button"
              disabled={sendBusy || !canSend}
              onClick={handleSendToKitchen}
            >
              {sendBusy ? "Sending..." : "Send to Kitchen"}
            </button>
            <button
              className="secondary-button"
              onClick={() => setCancelModalOpen(true)}
            >
              Cancel Order
            </button>
          </>
        ) : null}

        <button
          className="pay-button"
          disabled={!canPay}
          onClick={onPay}
        >
          Proceed to Payment
        </button>
      </div>
    </aside>

    {cancelModalOpen && state.serverId && state.order && (
      <CancelOrderModal
        order={state.order}
        onClose={() => setCancelModalOpen(false)}
        onCancelled={() => handleCancelSuccess()}
      />
    )}
    </>
  );
}