import {
  Check,
  Printer,
  X,
} from "lucide-react";

import type { ReceiptData } from "./PaymentModal";

export function SuccessModal({
  receipt,
  onClose,
}: {
  receipt: ReceiptData;
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop">
      {/* NORMAL SCREEN RECEIPT */}
      <div className="success-modal screen-success">
        <button className="modal-close" onClick={onClose}>
          <X />
        </button>

        <div className="success-icon">
          <Check size={32} />
        </div>

        <p className="eyebrow">BILL READY</p>

        <h2>Order {receipt.orderNumber}</h2>

        <div className="receipt-screen">
          <div className="receipt-business">
            <strong>MY RESTAURANT</strong>
            <span>Restaurant POS</span>
          </div>

          <div className="receipt-line" />

          <div className="receipt-meta">
            <div>
              <span>Order</span>
              <strong>{receipt.orderNumber}</strong>
            </div>

            <div>
              <span>Date</span>
              <strong>{receipt.date}</strong>
            </div>

            <div>
              <span>Time</span>
              <strong>{receipt.time}</strong>
            </div>
          </div>

          <div className="receipt-line" />

          <div className="receipt-items">
            {receipt.cart.map((item) => (
              <div className="receipt-item" key={item.product.id}>
                <div>
                  <strong>{item.product.name}</strong>
                  <span>
                    {item.quantity} × Rs. {Number(item.product.price).toFixed(2)}
                  </span>
                </div>

                <strong>
                  Rs. {Number(item.product.price * item.quantity).toFixed(2)}
                </strong>
              </div>
            ))}
          </div>

          <div className="receipt-line" />

          <div className="receipt-summary">
            <div>
              <span>Subtotal</span>
              <strong>Rs. {Number(receipt.subtotal).toFixed(2)}</strong>
            </div>

            <div>
              <span>Discount</span>
              <strong>- Rs. {Number(receipt.discount).toFixed(2)}</strong>
            </div>

            <div>
              <span>Tax</span>
              <strong>Rs. {Number(receipt.tax).toFixed(2)}</strong>
            </div>

            <div className="receipt-grand-total">
              <span>TOTAL</span>
              <strong>Rs. {Number(receipt.total).toFixed(2)}</strong>
            </div>
          </div>

          <div className="receipt-line" />

          <div className="receipt-payment">
            <div>
              <span>Payment</span>
              <strong>{receipt.paymentMethod}</strong>
            </div>

            {receipt.paymentMethod === "CASH" && (
              <>
                <div>
                  <span>Received</span>
                  <strong>Rs. {Number(receipt.amountReceived).toFixed(2)}</strong>
                </div>

                <div>
                  <span>Change</span>
                  <strong>Rs. {Number(receipt.change).toFixed(2)}</strong>
                </div>
              </>
            )}
          </div>

          <div className="receipt-line" />

          <div className="receipt-thankyou">
            <strong>THANK YOU!</strong>
            <span>Please visit us again.</span>
          </div>
        </div>

        <div className="success-actions">
          <button className="secondary-button" onClick={() => window.print()}>
            <Printer size={18} /> Print Receipt
          </button>

          <button className="pay-button" onClick={onClose}>
            New Order
          </button>
        </div>

        <button className="text-button" onClick={onClose}>
          <X size={16} /> Close
        </button>
      </div>

      {/* THERMAL RECEIPT (printed only) */}
      <div className="print-receipt">
        <div className="receipt-header">
          <h1>MY RESTAURANT</h1>
          <p>Restaurant POS</p>
        </div>

        <div className="receipt-divider">--------------------------------</div>

        <div className="receipt-info">
          <div>
            <span>Order</span>
            <strong>{receipt.orderNumber}</strong>
          </div>
          <div>
            <span>Date</span>
            <strong>{receipt.date}</strong>
          </div>
          <div>
            <span>Time</span>
            <strong>{receipt.time}</strong>
          </div>
        </div>

        <div className="receipt-divider">--------------------------------</div>

        <div className="thermal-items-head">
          <div className="thermal-col-name">ITEM</div>
          <div className="thermal-col-qty">QTY</div>
          <div className="thermal-col-price">PRICE</div>
          <div className="thermal-col-total">TOTAL</div>
        </div>

        <div className="receipt-divider">--------------------------------</div>

        {receipt.cart.map((item) => {
          const qty = Number(item.quantity);
          const unit = Number(item.product.price);
          const line = Number(qty * unit);

          return (
            <div className="thermal-item" key={item.product.id}>
              <div className="thermal-item-name">{item.product.name}</div>
              <div className="thermal-item-row">
                <div className="thermal-col-name" />
                <div className="thermal-col-qty">{qty}</div>
                <div className="thermal-col-price">{unit.toFixed(2)}</div>
                <div className="thermal-col-total">{line.toFixed(2)}</div>
              </div>
            </div>
          );
        })}

        <div className="receipt-divider">--------------------------------</div>

        <div className="thermal-summary">
          <div>
            <span>Subtotal</span>
            <strong>Rs. {Number(receipt.subtotal).toFixed(2)}</strong>
          </div>

          <div>
            <span>Discount</span>
            <strong>- Rs. {Number(receipt.discount).toFixed(2)}</strong>
          </div>

          <div>
            <span>Tax</span>
            <strong>Rs. {Number(receipt.tax).toFixed(2)}</strong>
          </div>

          <div className="thermal-total">
            <span>TOTAL</span>
            <strong>Rs. {Number(receipt.total).toFixed(2)}</strong>
          </div>
        </div>

        <div className="receipt-divider">--------------------------------</div>

        <div className="thermal-payment">
          <div>
            <span>Payment Method</span>
            <strong>{receipt.paymentMethod}</strong>
          </div>
          <div className="thermal-payable">
            <span>PAYABLE</span>
            <strong>Rs. {Number(receipt.total).toFixed(2)}</strong>
          </div>
        </div>

        <div className="receipt-divider">--------------------------------</div>

        <div className="receipt-footer">
          <p>THANK YOU!</p>
          <p>Please visit us again.</p>
        </div>
      </div>
    </div>
  );
}
