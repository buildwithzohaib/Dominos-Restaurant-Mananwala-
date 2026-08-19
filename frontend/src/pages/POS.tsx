import { Search } from "lucide-react";
import { useContext, useEffect, useMemo, useState } from "react";

import { CategoryBar } from "../components/CategoryBar";
import { OrderPanel } from "../components/OrderPanel";
import {
  PaymentModal,
  type ReceiptData,
} from "../components/PaymentModal";
import { ProductCard } from "../components/ProductCard";
import { SuccessModal } from "../components/SuccessModal";

import { usePOS } from "../context/POSContext";
import { useCatalog } from "../context/CatalogContext";
import { SettingsContext } from "../context/SettingsContext";
import { getRestaurantLetter } from "../utils/restaurant";
import { isOrderNotOpenError } from "../utils/orderErrors";
import { api } from "../services/api";
import type { OrderType, Product, RestaurantTable } from "../types";

export function POS({ onActiveOrdersClick }: { onActiveOrdersClick?: () => void }) {
  const {
    addProduct,
    state,
    setOrderType,
    setTable,
    syncProducts,
    clear,
    addProductToDineIn,
  } = usePOS();

  const { catalogProducts, catalogCategories, tables, refresh } = useCatalog();

  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;

  const [addError, setAddError] = useState("");
  const [openOrderCount, setOpenOrderCount] = useState(0);

  // Fetch open order count
  const refreshOpenOrders = async () => {
    try {
      const orders = await api.getOrders({ status: "OPEN" });
      setOpenOrderCount(orders.length);
    } catch (e) {
      console.error("Failed to fetch open orders:", e);
    }
  };

  useEffect(() => {
    refreshOpenOrders();
    const interval = setInterval(refreshOpenOrders, 30000);
    return () => clearInterval(interval);
  }, []);

  // Handle adding product to DINE_IN order
  const handleAddProduct = async (product: Product) => {
    if (state.orderType === "DINE_IN") {
      if (!state.selectedTable) {
        setAddError("Select a table first");
        return;
      }
      try {
        setAddError("");
        const isNewOrder = !state.serverId;
        await addProductToDineIn(state.selectedTable.id, product);
        // If this was the first item (new order opened), update the count immediately
        if (isNewOrder) {
          refreshOpenOrders();
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Failed to add item";
        if (isOrderNotOpenError(msg)) {
          clear();
          setAddError("This tab is no longer open — it may have been paid or cancelled on another terminal.");
        } else {
          const detail = state.serverId && state.selectedTable ? ` The tab is open on ${state.selectedTable.name} and can be managed from Active Orders.` : "";
          setAddError(msg + detail);
        }
      }
    } else {
      addProduct(product);
    }
  };

  // Handle table switch with detach
  const handleTableChange = (newTable: RestaurantTable | null) => {
    if (state.serverId) {
      // Detach from the open order
      clear();
    }
    setTable(newTable);
  };

  // Handle order type switch with detach
  const handleOrderTypeChange = (type: OrderType) => {
    if (state.serverId) {
      // Detach from the open order
      clear();
    }
    setOrderType(type);
  };

  // Whenever the product list is refreshed (after an order or an inventory edit),
  // re-point any existing cart lines at the latest stock so a line added before a
  // concurrent sale can't still be checked out against stock that's gone (Phase 6).
  useEffect(() => {
    syncProducts(catalogProducts);
  }, [catalogProducts, syncProducts]);

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

    return catalogProducts.filter(
      (p) =>
        (
          category === "all" ||
          p.category_id === category
        ) &&
        (
          !q ||
          p.name_display
            .toLowerCase()
            .includes(q)
        )
    );
  }, [
    catalogProducts,
    category,
    query,
  ]);

  return (
    <div className="pos-page">

      {/* TOP BAR */}

      <header className="topbar">

        <div className="brand">

          <div className="brand-mark">
            {getRestaurantLetter(settings?.restaurant_name)}
          </div>

          <div>
            <strong>
              {settings?.restaurant_name || "Loading..."}
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
                  handleOrderTypeChange(type)
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
                handleTableChange(
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
                  {table.name}
                </option>

              ))}

            </select>

          )}

        </div>


        {openOrderCount > 0 && (
          <button
            className="topbar-indicator"
            onClick={onActiveOrdersClick}
            title="View active orders"
          >
            Open orders: {openOrderCount}
          </button>
        )}

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

      {addError && (
        <div className="error-banner">
          {addError}
        </div>
      )}

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
            categories={catalogCategories}
            selected={category}
            onChange={setCategory}
          />


          <div className="product-grid">

            {filtered.map((product) => (

              <ProductCard
                key={product.id}
                product={product}
                onAdd={handleAddProduct}
              />

            ))}

          </div>

        </section>


        <OrderPanel
          onPay={() =>
            setPaymentOpen(true)
          }
          onCancelSuccess={refreshOpenOrders}
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
            refresh();
          }}

          onPaymentSuccess={refreshOpenOrders}
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