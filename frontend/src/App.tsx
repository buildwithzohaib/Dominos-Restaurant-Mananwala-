import { useCallback, useContext, useEffect, useState } from "react";
import { ClipboardList, LayoutDashboard, Package, ShoppingCart, Settings as SettingsIcon } from "lucide-react";
import { SettingsProvider, SettingsContext } from "./context/SettingsContext";
import { POSProvider } from "./context/POSContext";
import { api } from "./services/api";
import { POS } from "./pages/POS";
import { Orders } from "./pages/Orders";
import { Inventory } from "./pages/Inventory";
import { Dashboard } from "./pages/Dashboard";
import { Products } from "./pages/Products";
import { Settings } from "./pages/Settings";
import { getRestaurantLetter } from "./utils/restaurant";
import type { Category, Product } from "./types";

function AppContent() {
  const [page, setPage] = useState<"pos" | "orders" | "inventory" | "dashboard" | "products" | "settings">("pos");
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState("");

  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;

  useEffect(() => {
    Promise.all([api.getCategories(), api.getCatalogProducts()])
      .then(([c, p]) => {
        setCategories(c);
        setProducts(p);
      })
      .catch((e) =>
        setError(
          e instanceof Error
            ? e.message
            : "Could not connect to backend"
        )
      );
  }, []);

  // Products (price/stock) come from one backend source of truth. Re-fetch after a
  // completed order or an inventory edit so POS never sells against a stale stock count.
  const refreshProducts = useCallback(() => {
    api.getCatalogProducts().then(setProducts).catch(() => {});
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="sidebar-logo"
          onClick={() => setPage("pos")}
          title="Go to POS"
        >
          {getRestaurantLetter(settings?.restaurant_name)}
        </button>
        <nav>
          <button
            className={page === "pos" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("pos")}
          >
            <ShoppingCart size={21} />
            <span>POS</span>
          </button>
          <button
            className={page === "orders" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("orders")}
          >
            <ClipboardList size={21} />
            <span>Orders</span>
          </button>
          <button
            className={page === "inventory" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("inventory")}
          >
            <Package size={21} />
            <span>Inventory</span>
          </button>
          <button
            className={page === "dashboard" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("dashboard")}
          >
            <LayoutDashboard size={21} />
            <span>Overview</span>
          </button>
          <button
            className={page === "products" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("products")}
          >
            <Package size={21} />
            <span>Products</span>
          </button>
          <button
            className={page === "settings" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("settings")}
          >
            <SettingsIcon size={21} />
            <span>Settings</span>
          </button>
        </nav>
        <div className="sidebar-footer">v1.0</div>
      </aside>
      <div className="main-shell">
        {error && (
          <div className="connection-banner">
            Backend connection failed: {error}
          </div>
        )}
        {page === "pos" && (
          <POS
            categories={categories}
            products={products}
            onOrderComplete={refreshProducts}
          />
        )}
        {page === "orders" && <Orders />}
        {page === "inventory" && <Inventory onChange={refreshProducts} />}
        {page === "dashboard" && <Dashboard />}
        {page === "products" && <Products />}
        {page === "settings" && <Settings />}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <SettingsProvider>
      <POSProvider>
        <AppContent />
      </POSProvider>
    </SettingsProvider>
  );
}
