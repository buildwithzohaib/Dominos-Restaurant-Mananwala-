import { useContext, useState } from "react";
import { ClipboardList, LayoutDashboard, Package, ShoppingCart, Settings as SettingsIcon } from "lucide-react";
import { SettingsProvider, SettingsContext } from "./context/SettingsContext";
import { CatalogProvider } from "./context/CatalogContext";
import { POSProvider } from "./context/POSContext";
import { POS } from "./pages/POS";
import { Orders } from "./pages/Orders";
import { Inventory } from "./pages/Inventory";
import { Dashboard } from "./pages/Dashboard";
import { Products } from "./pages/Products";
import { Settings } from "./pages/Settings";
import { getRestaurantLetter } from "./utils/restaurant";

function AppContent() {
  const [page, setPage] = useState<"pos" | "orders" | "inventory" | "dashboard" | "products" | "settings">("pos");
  const [error, setError] = useState("");

  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;

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
        {page === "pos" && <POS />}
        {page === "orders" && <Orders />}
        {page === "inventory" && <Inventory />}
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
      <CatalogProvider>
        <POSProvider>
          <AppContent />
        </POSProvider>
      </CatalogProvider>
    </SettingsProvider>
  );
}
