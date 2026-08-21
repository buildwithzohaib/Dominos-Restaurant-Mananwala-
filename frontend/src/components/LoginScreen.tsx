import { useState, useEffect } from "react";
import { useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import { api } from "../services/api";

export function LoginScreen() {
  const auth = useContext(AuthContext);
  const [name, setName] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [restaurantName, setRestaurantName] = useState("Restaurant POS");

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const settings = await api.getSettings();
        setRestaurantName(settings.restaurant_name);
      } catch {
        // Keep default fallback if fetch fails
      }
    };
    fetchSettings();
  }, []);

  if (!auth) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      await auth.login(name, pin);
    } catch (err) {
      // Show a friendly error message that doesn't reveal which field was wrong
      setError("Login failed. Please check your name and PIN.");
      setPin("");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-container">
        <div className="login-header">
          <h1>{restaurantName}</h1>
          <p>Staff Login</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="name">Name</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter your name"
              disabled={isLoading}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="pin">PIN</label>
            <input
              id="pin"
              type="password"
              inputMode="numeric"
              maxLength={4}
              value={pin}
              onChange={(e) => {
                const val = e.target.value.replace(/[^0-9]/g, "");
                setPin(val.slice(0, 4));
              }}
              placeholder="0000"
              disabled={isLoading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={isLoading || !name.trim() || pin.length !== 4}>
            {isLoading ? "Logging in..." : "Login"}
          </button>
        </form>
      </div>
    </div>
  );
}
