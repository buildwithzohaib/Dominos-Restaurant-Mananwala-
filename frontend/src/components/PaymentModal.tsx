import { useState } from "react";
import {
  CreditCard,
  Banknote,
  CircleDollarSign,
  X,
} from "lucide-react";

import { api } from "../services/api";
import { usePOS } from "../context/POSContext";
import type { PaymentMethod, Product } from "../types";

type ReceiptCartItem = {
  product: Product;
  quantity: number;
};

export type ReceiptData = {
  orderNumber: string;
  cart: ReceiptCartItem[];

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

  const [received, setReceived] = useState(Number(total));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const change = Math.max(
    0,
    Number(received) - Number(total)
  );

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

        discount: Number(discount),
        tax_rate: Number(state.taxRate),

        payment_method: state.paymentMethod,

        amount_received:
          state.paymentMethod === "CASH"
            ? Number(received)
            : Number(total),
      });

      const now = new Date();

      const receipt: ReceiptData = {
        orderNumber: o.order_number,

        cart: state.cart.map((item) => ({
          product: item.product,
          quantity: item.quantity,
        })),

        subtotal: Number(subtotal),
        discount: Number(discount),
        tax: Number(tax),
        total: Number(total),

        paymentMethod: state.paymentMethod,

        amountReceived:
          state.paymentMethod === "CASH"
            ? Number(received)
            : Number(total),

        change:
          state.paymentMethod === "CASH"
            ? Number(change)
            : 0,

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
            Rs. {Number(total).toFixed(2)}
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
              min={Number(total)}
              value={received}
              onChange={(e) =>
                setReceived(
                  Number(e.target.value)
                )
              }
            />
          </label>
        )}

        {state.paymentMethod === "CASH" && (
          <div className="change-box">
            <span>
              Change
            </span>

            <strong>
              Rs. {Number(change).toFixed(2)}
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
              Number(received) < Number(total)
            )
          }
          onClick={pay}
        >
          {busy
            ? "Processing..."
            : "Complete Payment"}
        </button>

        <p className="payment-note">
          Subtotal Rs.{" "}
          {Number(subtotal).toFixed(2)}
          {" · "}
          Tax Rs.{" "}
          {Number(tax).toFixed(2)}
        </p>

      </div>
    </div>
  );
}