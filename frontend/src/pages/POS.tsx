import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { CategoryBar } from "../components/CategoryBar";
import { OrderPanel } from "../components/OrderPanel";
import {
  PaymentModal,
  type ReceiptData,
} from "../components/PaymentModal";
import { ProductCard } from "../components/ProductCard";
import { SuccessModal } from "../components/SuccessModal";

import { usePOS } from "../context/POSContext";
import { tables } from "../data/tables";

import type {
  Category,
  Product,
} from "../types";

export function POS({
  categories,
  products,
  onOrderComplete,
}: {
  categories: Category[];
  products: Product[];
  onOrderComplete?: () => void;
}) {
  const {
    addProduct,
    state,
    setOrderType,
    setTable,
    syncProducts,
  } = usePOS();

  // Whenever the product list is refreshed (after an order or an inventory edit),
  // re-point any existing cart lines at the latest stock so a line added before a
  // concurrent sale can't still be checked out against stock that's gone (Phase 6).
  useEffect(() => {
    syncProducts(products);
  }, [products, syncProducts]);

  const [category, setCategory] =
    useState<number | "all">("all");

  const [query, setQuery] =
    useState("");

  const [paymentOpen, setPaymentOpen] =
    useState(false);

  const [success, setSuccess] =
    useState<ReceiptData | null>(null);

  const filtered = useMemo(() => {
    const q = query
      .toLowerCase()
      .trim();

    return products.filter(
      (p) =>
        (
          category === "all" ||
          p.category_id === category
        ) &&
        (
          !q ||
          p.name
            .toLowerCase()
            .includes(q)
        )
    );
  }, [
    products,
    category,
    query,
  ]);

  return (
    <div className="pos-page">

      {/* TOP BAR */}

      <header className="topbar">

        <div className="brand">

          <div className="brand-mark">
            M
          </div>

          <div>
            <strong>
              My Restaurant
            </strong>

            <span>
              POS Terminal
            </span>
          </div>

        </div>


        <div className="topbar-center">

          <div className="order-type-switcher">

            {(
              [
                "DINE_IN",
                "TAKEAWAY",
                "DELIVERY",
              ] as const
            ).map((type) => (

              <button
                key={type}
                className={
                  state.orderType === type
                    ? "active"
                    : ""
                }
                onClick={() =>
                  setOrderType(type)
                }
              >
                {type === "DINE_IN"
                  ? "Dine In"
                  : type === "TAKEAWAY"
                  ? "Takeaway"
                  : "Delivery"}
              </button>

            ))}

          </div>


          {state.orderType === "DINE_IN" && (

            <select
              className="table-select"
              value={
                state.selectedTable?.id ?? ""
              }
              onChange={(e) =>
                setTable(
                  tables.find(
                    (table) =>
                      table.id ===
                      Number(e.target.value)
                  ) ?? null
                )
              }
            >

              <option value="">
                Select table
              </option>

              {tables.map((table) => (

                <option
                  key={table.id}
                  value={table.id}
                >
                  {table.name} ·{" "}
                  {table.seats} seats
                </option>

              ))}

            </select>

          )}

        </div>


        <div className="topbar-user">

          <div className="avatar">
            C
          </div>

          <div>
            <strong>
              Cashier
            </strong>

            <span>
              Online
            </span>
          </div>

        </div>

      </header>


      {/* POS MAIN AREA */}

      <main className="pos-layout">

        <section className="menu-area">

          <div className="menu-header">

            <div>

              <p className="eyebrow">
                MENU
              </p>

              <h1>
                Choose items
              </h1>

            </div>


            <div className="search-box">

              <Search size={18} />

              <input
                value={query}
                onChange={(e) =>
                  setQuery(e.target.value)
                }
                placeholder="Search menu..."
              />

            </div>

          </div>


          <CategoryBar
            categories={categories}
            selected={category}
            onChange={setCategory}
          />


          <div className="product-grid">

            {filtered.map((product) => (

              <ProductCard
                key={product.id}
                product={product}
                onAdd={addProduct}
              />

            ))}

          </div>

        </section>


        <OrderPanel
          onPay={() =>
            setPaymentOpen(true)
          }
        />

      </main>


      {/* PAYMENT */}

      {paymentOpen && (

        <PaymentModal
          onClose={() =>
            setPaymentOpen(false)
          }

          onSuccess={(receipt) => {
            setPaymentOpen(false);
            setSuccess(receipt);
            // Stock was decremented on the backend as part of the completed order;
            // refetch so the menu/cart never sell against a now-stale stock count.
            onOrderComplete?.();
          }}
        />

      )}


      {/* RECEIPT */}

      {success && (

        <SuccessModal
          receipt={success}
          onClose={() =>
            setSuccess(null)
          }
        />

      )}

    </div>
  );
}