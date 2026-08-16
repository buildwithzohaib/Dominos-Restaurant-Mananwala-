import {
  Check,
  Printer,
  X,
} from "lucide-react";

import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { useContext } from "react";
import { SettingsContext } from "../context/SettingsContext";
import type { ReceiptData } from "./PaymentModal";

export function SuccessModal({
  receipt,
  onClose,
}: {
  receipt: ReceiptData;
  onClose: () => void;
}) {
  const formatCurrency = useCurrencyFormat();
  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;

  // Default values while settings load
  const restaurantName = settings?.restaurant_name || "MY RESTAURANT";
  const footerText = settings?.receipt_footer_text || "Please visit us again.";
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
            <strong>{restaurantName}</strong>
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
            {receipt.items.map((item) => (
              <div className="receipt-item" key={item.id}>
                <div>
                  <strong>{item.product_name}</strong>
                  <span>
                    {item.quantity} × {formatCurrency(item.price)}
                  </span>
                </div>

                <strong>
                  {formatCurrency(item.line_total)}
                </strong>
              </div>
            ))}
          </div>

          <div className="receipt-line" />

          <div className="receipt-summary">
            <div>
              <span>Subtotal</span>
              <strong>{formatCurrency(receipt.subtotal)}</strong>
            </div>

            <div>
              <span>Discount</span>
              <strong>- {formatCurrency(receipt.discount)}</strong>
            </div>

            <div>
              <span>Tax</span>
              <strong>{formatCurrency(receipt.tax)}</strong>
            </div>

            <div className="receipt-grand-total">
              <span>TOTAL</span>
              <strong>{formatCurrency(receipt.total)}</strong>
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
                  <strong>{formatCurrency(receipt.amountReceived)}</strong>
                </div>

                <div>
                  <span>Change</span>
                  <strong>{formatCurrency(receipt.change)}</strong>
                </div>
              </>
            )}
          </div>

          <div className="receipt-line" />

          <div className="receipt-thankyou">
            <strong>THANK YOU!</strong>
            <span>{footerText}</span>
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
          <h1>{restaurantName}</h1>
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

        {receipt.items.map((item) => (
          <div className="thermal-item" key={item.id}>
            <div className="thermal-item-name">{item.product_name}</div>
            <div className="thermal-item-row">
              <div className="thermal-col-name" />
              <div className="thermal-col-qty">{item.quantity}</div>
              <div className="thermal-col-price">{formatCurrency(item.price)}</div>
              <div className="thermal-col-total">{formatCurrency(item.line_total)}</div>
            </div>
          </div>
        ))}

        <div className="receipt-divider">--------------------------------</div>

        <div className="thermal-summary">
          <div>
            <span>Subtotal</span>
            <strong>{formatCurrency(receipt.subtotal)}</strong>
          </div>

          <div>
            <span>Discount</span>
            <strong>- {formatCurrency(receipt.discount)}</strong>
          </div>

          <div>
            <span>Tax</span>
            <strong>{formatCurrency(receipt.tax)}</strong>
          </div>

          <div className="thermal-total">
            <span>TOTAL</span>
            <strong>{formatCurrency(receipt.total)}</strong>
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
            <strong>{formatCurrency(receipt.total)}</strong>
          </div>
        </div>

        <div className="receipt-divider">--------------------------------</div>

        <div className="receipt-footer">
          <p>THANK YOU!</p>
          <p>{footerText}</p>
        </div>
      </div>
    </div>
  );
}
