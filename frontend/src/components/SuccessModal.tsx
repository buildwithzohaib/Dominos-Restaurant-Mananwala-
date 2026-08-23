import {
  Check,
  Printer,
  X,
} from "lucide-react";

import { useCurrencyFormat } from "../hooks/useCurrencyFormat";
import { formatMoney } from "../utils/money";
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
  const restaurantAddress = settings?.restaurant_address || "";
  const restaurantPhone = settings?.restaurant_phone || "";
  const footerText = settings?.receipt_footer_text || "Please visit us again.";

  // Local helper: bare numbers without currency symbol
  const formatBare = (amount: number) => formatMoney(amount, "");
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
            {restaurantAddress && <p>{restaurantAddress}</p>}
            {restaurantPhone && <p>{restaurantPhone}</p>}
          </div>

          <div className="receipt-line" />

          {/* Delivery section: shown only for DELIVERY orders with address */}
          {receipt.orderType === "DELIVERY" && receipt.deliveryAddress && (
            <>
              <div className="receipt-delivery">
                <div className="receipt-delivery-header">
                  Delivery
                </div>
                {receipt.customerName && (
                  <div className="receipt-delivery-name">
                    {receipt.customerName}
                  </div>
                )}
                {receipt.customerPhone && (
                  <div className="receipt-delivery-phone">
                    {receipt.customerPhone}
                  </div>
                )}
                <div className="receipt-delivery-address">
                  {receipt.deliveryAddress}
                </div>
              </div>

              <div className="receipt-line" />
            </>
          )}

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

            {receipt.cashierName && (
              <div>
                <span>Cashier</span>
                <strong>{receipt.cashierName}</strong>
              </div>
            )}
          </div>

          <div className="receipt-line" />

          <div className="receipt-items-head">
            <div className="receipt-col-name">ITEM</div>
            <div className="receipt-col-qty">QTY</div>
            <div className="receipt-col-price">PRICE</div>
            <div className="receipt-col-total">TOTAL</div>
          </div>

          <div className="receipt-items">
            {receipt.items.map((item) => (
              <div className="receipt-item" key={item.id}>
                <div className="receipt-col-name">{item.product_name}</div>
                <div className="receipt-col-qty">{item.quantity}</div>
                <div className="receipt-col-price">{formatBare(item.price)}</div>
                <div className="receipt-col-total">{formatBare(item.line_total)}</div>
              </div>
            ))}
          </div>

          <div className="receipt-line" />

          <div className="receipt-summary">
            <div>
              <span>Subtotal</span>
              <strong>{formatBare(receipt.subtotal)}</strong>
            </div>

            <div>
              <span>Discount</span>
              <strong>- {formatBare(receipt.discount)}</strong>
            </div>

            {settings?.tax_enabled && (
              <div>
                <span>Tax</span>
                <strong>{formatBare(receipt.tax)}</strong>
              </div>
            )}

            {receipt.deliveryCharge > 0 && (
              <div>
                <span>Delivery</span>
                <strong>{formatBare(receipt.deliveryCharge)}</strong>
              </div>
            )}

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
                  <strong>{formatBare(receipt.amountReceived)}</strong>
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
          {restaurantAddress && <p>{restaurantAddress}</p>}
          {restaurantPhone && <p>{restaurantPhone}</p>}
        </div>

        <div className="receipt-divider">--------------------------------</div>

        {/* Delivery section: shown only for DELIVERY orders with address */}
        {receipt.orderType === "DELIVERY" && receipt.deliveryAddress && (
          <>
            <div className="thermal-delivery">
              <div className="thermal-delivery-header">
                Delivery
              </div>
              {receipt.customerName && (
                <div className="thermal-delivery-name">
                  {receipt.customerName}
                </div>
              )}
              {receipt.customerPhone && (
                <div className="thermal-delivery-phone">
                  {receipt.customerPhone}
                </div>
              )}
              <div className="thermal-delivery-address">
                {receipt.deliveryAddress}
              </div>
            </div>

            <div className="receipt-divider">--------------------------------</div>
          </>
        )}

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
          {receipt.cashierName && (
            <div>
              <span>Cashier</span>
              <strong>{receipt.cashierName}</strong>
            </div>
          )}
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
            <div className="thermal-col-name">{item.product_name}</div>
            <div className="thermal-col-qty">{item.quantity}</div>
            <div className="thermal-col-price">{formatBare(item.price)}</div>
            <div className="thermal-col-total">{formatBare(item.line_total)}</div>
          </div>
        ))}

        <div className="receipt-divider">--------------------------------</div>

        <div className="thermal-summary">
          <div>
            <span>Subtotal</span>
            <strong>{formatBare(receipt.subtotal)}</strong>
          </div>

          <div>
            <span>Discount</span>
            <strong>- {formatBare(receipt.discount)}</strong>
          </div>

          {settings?.tax_enabled && (
            <div>
              <span>Tax</span>
              <strong>{formatBare(receipt.tax)}</strong>
            </div>
          )}

          {receipt.deliveryCharge > 0 && (
            <div>
              <span>Delivery</span>
              <strong>{formatBare(receipt.deliveryCharge)}</strong>
            </div>
          )}

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
