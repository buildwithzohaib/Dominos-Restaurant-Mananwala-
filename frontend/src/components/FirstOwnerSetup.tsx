import { useState, useEffect } from "react";
import { useContext } from "react";
import { AuthContext } from "../context/AuthContext";
import { api } from "../services/api";

export function FirstOwnerSetup() {
  const auth = useContext(AuthContext);
  const [name, setName] = useState("");
  const [pin, setPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
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

    // Validation
    if (!name.trim()) {
      setError("Name is required");
      return;
    }

    if (pin.length !== 4 || !/^\d{4}$/.test(pin)) {
      setError("PIN must be exactly 4 digits");
      return;
    }

    if (pin !== confirmPin) {
      setError("PINs do not match");
      return;
    }

    setIsLoading(true);

    try {
      await auth.bootstrapOwner(name, pin);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create owner account";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };
  const pinValid = pin.length === 4 && /^\d{4}$/.test(pin);
  const pinsMatch = pin === confirmPin;
  const isFormValid = name.trim() && pinValid && pinsMatch;

  return (
    <div className="login-screen">
      <div className="login-container">
        <div className="login-header">
          <h1>{restaurantName}</h1>
          <p>Setup Owner Account</p>
        </div>

        <div className="setup-info">
          <p>Welcome! Create your Owner account to get started.</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="owner-name">Name</label>
            <input
              id="owner-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter owner name"
              disabled={isLoading}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="owner-pin">PIN (4 digits)</label>
            <input
              id="owner-pin"
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

          <div className="form-group">
            <label htmlFor="owner-confirm-pin">Confirm PIN</label>
            <input
              id="owner-confirm-pin"
              type="password"
              inputMode="numeric"
              maxLength={4}
              value={confirmPin}
              onChange={(e) => {
                const val = e.target.value.replace(/[^0-9]/g, "");
                setConfirmPin(val.slice(0, 4));
              }}
              placeholder="0000"
              disabled={isLoading}
            />
            {pin && confirmPin && !pinsMatch && (
              <div className="field-hint error">PINs do not match</div>
            )}
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={isLoading || !isFormValid}>
            {isLoading ? "Creating account..." : "Create Owner Account"}
          </button>
        </form>
      </div>
    </div>
  );
}
