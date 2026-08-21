import { useContext, useState } from "react";
import { Clock, ClipboardList, LayoutDashboard, Package, ShoppingCart, Settings as SettingsIcon, Users, LogOut, UserCog } from "lucide-react";
import { AuthProvider, AuthContext } from "./context/AuthContext";
import { SettingsProvider, SettingsContext } from "./context/SettingsContext";
import { CatalogProvider } from "./context/CatalogContext";
import { POSProvider } from "./context/POSContext";
import { LoginScreen } from "./components/LoginScreen";
import { FirstOwnerSetup } from "./components/FirstOwnerSetup";
import { POS } from "./pages/POS";
import { ActiveOrders } from "./pages/ActiveOrders";
import { Orders } from "./pages/Orders";
import { Inventory } from "./pages/Inventory";
import { Dashboard } from "./pages/Dashboard";
import { Products } from "./pages/Products";
import { Customers } from "./pages/Customers";
import { Staff } from "./pages/Staff";
import { Settings } from "./pages/Settings";
import { getRestaurantLetter } from "./utils/restaurant";
import type { Order } from "./types";

function AppContent() {
  const [page, setPage] = useState<"pos" | "activeorders" | "orders" | "inventory" | "dashboard" | "products" | "customers" | "staff" | "settings">("pos");
  const [error, setError] = useState("");

  const authContext = useContext(AuthContext);
  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;

  const handleLogout = async () => {
    try {
      await authContext?.logout();
    } catch (err) {
      console.error("Logout error:", err);
    }
  };

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
            className={page === "activeorders" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("activeorders")}
          >
            <Clock size={21} />
            <span>Active Orders</span>
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
            className={page === "customers" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("customers")}
          >
            <Users size={21} />
            <span>Customers</span>
          </button>
          {authContext?.user?.is_owner && (
            <button
              className={page === "staff" ? "nav-item active" : "nav-item"}
              onClick={() => setPage("staff")}
            >
              <UserCog size={21} />
              <span>Staff</span>
            </button>
          )}
          <button
            className={page === "settings" ? "nav-item active" : "nav-item"}
            onClick={() => setPage("settings")}
          >
            <SettingsIcon size={21} />
            <span>Settings</span>
          </button>
        </nav>
        <div className="sidebar-footer">
          {authContext?.user && (
            <div className="user-info">
              <span className="user-name">{authContext.user.name}</span>
              <button
                className="logout-btn"
                onClick={handleLogout}
                title="Logout"
                aria-label="Logout"
              >
                <LogOut size={18} />
              </button>
            </div>
          )}
        </div>
      </aside>
      <div className="main-shell">
        {error && (
          <div className="connection-banner">
            Backend connection failed: {error}
          </div>
        )}
        {page === "pos" && (
          <POS onActiveOrdersClick={() => setPage("activeorders")} />
        )}
        {page === "activeorders" && (
          <ActiveOrders
            onResume={() => {
              setPage("pos");
            }}
          />
        )}
        {page === "orders" && <Orders />}
        {page === "inventory" && <Inventory />}
        {page === "dashboard" && <Dashboard />}
        {page === "products" && <Products />}
        {page === "customers" && <Customers />}
        {page === "staff" && <Staff />}
        {page === "settings" && <Settings />}
      </div>
    </div>
  );
}

function AppWithAuth() {
  const auth = useContext(AuthContext);

  if (auth?.loading) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  if (auth?.needsBootstrap) {
    return <FirstOwnerSetup />;
  }

  if (!auth?.user) {
    return <LoginScreen />;
  }

  // User is logged in, render the full app
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

export default function App() {
  return (
    <AuthProvider>
      <AppWithAuth />
    </AuthProvider>
  );
}
