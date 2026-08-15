import { useState } from "react";
import { formatMoney } from "../utils/money";
import {
  CreditCard,
  Banknote,
  CircleDollarSign,
  X,
} from "lucide-react";

import { api } from "../services/api";
import { usePOS } from "../context/POSContext";
import { rupeesToPaisa, paisaToRupees } from "../utils/money";
import type { PaymentMethod, OrderItem } from "../types";

export type ReceiptData = {
  orderNumber: string;
  items: OrderItem[];

  subtotal: number;
  discount: number;
  tax: number;
  total: number;

  paymentMethod: PaymentMethod;
  amountReceived: number;
  change: number;

  date: string;
  time: string;
};

export function PaymentModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: (receipt: ReceiptData) => void;
}) {
  const {
    state,
    subtotal,
    discount,
    tax,
    total,
    clear,
    setPaymentMethod,
  } = usePOS();

  const [receivedText, setReceivedText] = useState(String(paisaToRupees(total)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const received = rupeesToPaisa(parseFloat(receivedText) || 0);
  const change = Math.max(0, received - total);

  async function pay() {
    setBusy(true);
    setError("");

    try {
      const o = await api.createOrder({
        order_type: state.orderType,
        table_id: state.selectedTable?.id ?? null,

        items: state.cart.map((i) => ({
          product_id: i.product.id,
          quantity: i.quantity,
        })),

        discount: discount,
        tax_rate: state.taxRate,

        payment_method: state.paymentMethod,

        amount_received:
          state.paymentMethod === "CASH"
            ? received
            : total,
      });

      const now = new Date();

      const receipt: ReceiptData = {
        orderNumber: o.order_number,

        items: o.items,

        subtotal: o.subtotal,
        discount: o.discount,
        tax: o.tax,
        total: o.total,

        paymentMethod: o.payment_method,

        amountReceived: o.amount_received,

        change: o.change_amount,

        date: now.toLocaleDateString(),

        time: now.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      clear();

      onSuccess(receipt);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Payment failed"
      );
    } finally {
      setBusy(false);
    }
  }

  const methods: [
    PaymentMethod,
    string,
    typeof Banknote
  ][] = [
    ["CASH", "Cash", Banknote],
    ["CARD", "Card", CreditCard],
    ["OTHER", "Other", CircleDollarSign],
  ];

  return (
    <div className="modal-backdrop">
      <div className="payment-modal">

        <button
          className="modal-close"
          onClick={onClose}
        >
          <X />
        </button>

        <p className="eyebrow">
          PAYMENT
        </p>

        <h2>
          Complete Order
        </h2>

        <div className="payment-total">
          <span>
            Total due
          </span>

          <strong>
            {formatMoney(total)}
          </strong>
        </div>

        <div className="payment-methods">
          {methods.map(([value, label, Icon]) => (
            <button
              key={value}
              className={
                state.paymentMethod === value
                  ? "payment-method active"
                  : "payment-method"
              }
              onClick={() =>
                setPaymentMethod(value)
              }
            >
              <Icon size={20} />
              {label}
            </button>
          ))}
        </div>

        {state.paymentMethod === "CASH" && (
          <label className="large-input">
            Amount received

            <input
              autoFocus
              type="number"
              step="0.01"
              value={receivedText}
              onChange={(e) => setReceivedText(e.target.value)}
            />
          </label>
        )}

        {state.paymentMethod === "CASH" && (
          <div className="change-box">
            <span>
              Change
            </span>

            <strong>
              {formatMoney(change)}
            </strong>
          </div>
        )}

        {error && (
          <div className="error-box">
            {error}
          </div>
        )}

        <button
          className="pay-button"
          disabled={
            busy ||
            (
              state.paymentMethod === "CASH" &&
              received < total
            )
          }
          onClick={pay}
        >
          {busy
            ? "Processing..."
            : "Complete Payment"}
        </button>

        <p className="payment-note">
          Subtotal {formatMoney(subtotal)}
          {" · "}
          Tax {formatMoney(tax)}
        </p>

      </div>
    </div>
  );
}