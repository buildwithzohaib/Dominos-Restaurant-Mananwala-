import { UserCog, Lock, Loader, Users, Key, PowerOff, Power } from "lucide-react";
import { useState, useEffect, useContext } from "react";
import { api } from "../services/api";
import { AuthContext } from "../context/AuthContext";
import type { User } from "../types";

// Get CSS token colors at runtime
function getCSSToken(tokenName: string): string {
  const css = getComputedStyle(document.documentElement);
  return css.getPropertyValue(tokenName).trim();
}

export function Staff() {
  const authContext = useContext(AuthContext);
  const currentUser = authContext?.user;

  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Add staff form state
  const [newStaff, setNewStaff] = useState({
    name: "",
    pin: "",
    confirmPin: "",
    can_cancel: false,
    can_discount: false,
    can_manage_settings: false,
  });
  const [formError, setFormError] = useState("");

  // Reset PIN modal state
  const [resetPinUserId, setResetPinUserId] = useState<number | null>(null);
  const [resetPinForm, setResetPinForm] = useState({
    new_pin: "",
    confirm_pin: "",
  });
  const [resetPinError, setResetPinError] = useState("");

  // Load staff on mount
  useEffect(() => {
    loadStaff();
  }, []);

  const loadStaff = async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await api.listUsers();
      setUsers(data.sort((a, b) => {
        if (a.is_active !== b.is_active) return b.is_active ? 1 : -1;
        return a.name.localeCompare(b.name);
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load staff");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");

    if (!newStaff.name.trim()) {
      setFormError("Name is required");
      return;
    }

    if (newStaff.pin.length !== 4 || !/^\d{4}$/.test(newStaff.pin)) {
      setFormError("PIN must be exactly 4 digits");
      return;
    }

    if (newStaff.pin !== newStaff.confirmPin) {
      setFormError("PINs do not match");
      return;
    }

    setIsCreating(true);

    try {
      await api.createUser({
        name: newStaff.name,
        pin: newStaff.pin,
        can_cancel: newStaff.can_cancel,
        can_discount: newStaff.can_discount,
        can_manage_settings: newStaff.can_manage_settings,
        is_owner: false,
      });

      setNewStaff({
        name: "",
        pin: "",
        confirmPin: "",
        can_cancel: false,
        can_discount: false,
        can_manage_settings: false,
      });

      await loadStaff();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Failed to create staff");
    } finally {
      setIsCreating(false);
    }
  };

  const handleTogglePermission = async (
    userId: number,
    permission: "can_cancel" | "can_discount" | "can_manage_settings",
    currentValue: boolean
  ) => {
    try {
      await api.updateUserPermissions(userId, {
        [permission]: !currentValue,
      });
      await loadStaff();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update permissions");
    }
  };

  const handleToggleActive = async (user: User) => {
    try {
      if (user.is_active) {
        await api.deactivateUser(user.id);
      } else {
        await api.reactivateUser(user.id);
      }
      await loadStaff();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update user");
    }
  };

  const handleResetPin = async () => {
    setResetPinError("");

    if (resetPinForm.new_pin.length !== 4 || !/^\d{4}$/.test(resetPinForm.new_pin)) {
      setResetPinError("PIN must be exactly 4 digits");
      return;
    }

    if (resetPinForm.new_pin !== resetPinForm.confirm_pin) {
      setResetPinError("PINs do not match");
      return;
    }

    try {
      if (resetPinUserId) {
        await api.resetUserPin(resetPinUserId, resetPinForm.new_pin);
        setResetPinUserId(null);
        setResetPinForm({ new_pin: "", confirm_pin: "" });
        await loadStaff();
      }
    } catch (e) {
      setResetPinError(e instanceof Error ? e.message : "Failed to reset PIN");
    }
  };

  return (
    <div className="products-page">
      <div className="page-header-toolbar">
        <div className="page-header">
          <div>
            <p className="eyebrow">ADMINISTRATION</p>
            <h1>Staff Management</h1>
          </div>
        </div>
      </div>

      <div className="inventory-card">
        {isLoading ? (
          <div className="loading">
            <Loader size={24} className="spinner" />
            Loading staff...
          </div>
        ) : error ? (
          <div className="error-box">{error}</div>
        ) : users.length === 0 ? (
          <div className="loading">
            <Users size={48} style={{ marginBottom: "16px", opacity: 0.3 }} />
            <p>No staff accounts yet.</p>
          </div>
        ) : (
          <>
            <div className="inventory-head">
              <span>Name</span>
              <span>Role</span>
              <span>Cancel</span>
              <span>Discount</span>
              <span>Settings</span>
              <span>Status</span>
              <span />
            </div>

            {users.map((user) => (
              <div
                className={`inventory-row ${
                  !user.is_active ? "disabled-row" : ""
                }`}
                key={user.id}
              >
                <span>
                  <strong className="item-name">{user.name}</strong>
                </span>

                <span>{user.is_owner ? "Owner" : "Staff"}</span>

                {user.is_owner ? (
                  <>
                    <span style={{ color: getCSSToken("--success"), fontSize: "12px" }}>Full access</span>
                    <span style={{ color: getCSSToken("--success"), fontSize: "12px" }}>Full access</span>
                    <span style={{ color: getCSSToken("--success"), fontSize: "12px" }}>Full access</span>
                  </>
                ) : (
                  <>
                    <span>
                      <input
                        type="checkbox"
                        checked={user.can_cancel}
                        onChange={() =>
                          handleTogglePermission(user.id, "can_cancel", user.can_cancel)
                        }
                        disabled={!user.is_active}
                      />
                    </span>
                    <span>
                      <input
                        type="checkbox"
                        checked={user.can_discount}
                        onChange={() =>
                          handleTogglePermission(user.id, "can_discount", user.can_discount)
                        }
                        disabled={!user.is_active}
                      />
                    </span>
                    <span>
                      <input
                        type="checkbox"
                        checked={user.can_manage_settings}
                        onChange={() =>
                          handleTogglePermission(
                            user.id,
                            "can_manage_settings",
                            user.can_manage_settings
                          )
                        }
                        disabled={!user.is_active}
                      />
                    </span>
                  </>
                )}

                <span>
                  <span
                    className="status-badge"
                    style={{
                      background: user.is_active ? getCSSToken("--success-bg") : getCSSToken("--danger-bg"),
                      color: user.is_active ? getCSSToken("--success-text") : getCSSToken("--danger-text"),
                    }}
                  >
                    {user.is_active ? "Active" : "Inactive"}
                  </span>
                </span>

                <span>
                  <div className="row-actions">
                    <button
                      className="row-action-button"
                      onClick={() => {
                        setResetPinUserId(user.id);
                        setResetPinForm({ new_pin: "", confirm_pin: "" });
                        setResetPinError("");
                      }}
                      title="Reset PIN"
                      disabled={!user.is_active}
                    >
                      <Key size={16} />
                    </button>

                    {currentUser?.id !== user.id && (
                      <button
                        className="row-action-button"
                        onClick={() => handleToggleActive(user)}
                        title={user.is_active ? "Deactivate" : "Reactivate"}
                      >
                        {user.is_active ? (
                          <PowerOff size={16} />
                        ) : (
                          <Power size={16} />
                        )}
                      </button>
                    )}
                  </div>
                </span>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Add Staff Form */}
      <div className="settings-form" style={{ marginTop: "32px" }}>
        <fieldset>
          <legend>Add Staff Member</legend>

          {formError && <div className="error-box">{formError}</div>}

          <form onSubmit={handleCreateStaff}>
            <label>
              Name
              <input
                type="text"
                value={newStaff.name}
                onChange={(e) =>
                  setNewStaff({ ...newStaff, name: e.target.value })
                }
                disabled={isCreating}
              />
            </label>

            <label>
              PIN (4 digits)
              <input
                type="password"
                inputMode="numeric"
                maxLength={4}
                value={newStaff.pin}
                onChange={(e) => {
                  const val = e.target.value.replace(/[^0-9]/g, "");
                  setNewStaff({ ...newStaff, pin: val.slice(0, 4) });
                }}
                disabled={isCreating}
              />
            </label>

            <label>
              Confirm PIN
              <input
                type="password"
                inputMode="numeric"
                maxLength={4}
                value={newStaff.confirmPin}
                onChange={(e) => {
                  const val = e.target.value.replace(/[^0-9]/g, "");
                  setNewStaff({ ...newStaff, confirmPin: val.slice(0, 4) });
                }}
                disabled={isCreating}
              />
            </label>

            <div className="permissions-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={newStaff.can_cancel}
                  onChange={(e) =>
                    setNewStaff({ ...newStaff, can_cancel: e.target.checked })
                  }
                  disabled={isCreating}
                />
                Can cancel orders
              </label>

              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={newStaff.can_discount}
                  onChange={(e) =>
                    setNewStaff({ ...newStaff, can_discount: e.target.checked })
                  }
                  disabled={isCreating}
                />
                Can apply discounts
              </label>

              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={newStaff.can_manage_settings}
                  onChange={(e) =>
                    setNewStaff({
                      ...newStaff,
                      can_manage_settings: e.target.checked,
                    })
                  }
                  disabled={isCreating}
                />
                Can change settings
              </label>
            </div>

            <div className="settings-actions">
              <button
                type="submit"
                className="pay-button"
                disabled={isCreating}
              >
                {isCreating ? "Creating..." : "Add Staff Member"}
              </button>
            </div>
          </form>
        </fieldset>
      </div>

      {/* Reset PIN Modal */}
      {resetPinUserId !== null && (
        <div className="modal-backdrop">
          <div
            className="inventory-modal"
            style={{
              background: "white",
              borderRadius: "16px",
              padding: "28px",
              boxShadow: "0 25px 70px rgba(0,0,0,0.15)",
            }}
          >
            <h2 style={{ margin: "0 0 20px 0", fontSize: "16px" }}>
              Reset PIN
            </h2>

            <p
              style={{
                fontSize: "13px",
                color: getCSSToken("--text-secondary"),
                marginBottom: "20px",
                lineHeight: "1.5",
              }}
            >
              The user will be logged out of all devices after the PIN is reset.
            </p>

            {resetPinError && (
              <div className="error-box" style={{ marginBottom: "16px" }}>
                {resetPinError}
              </div>
            )}

            <div className="modal-field-grid">
              <div className="modal-field full">
                <label htmlFor="new-pin-modal">New PIN (4 digits)</label>
                <input
                  id="new-pin-modal"
                  type="password"
                  inputMode="numeric"
                  maxLength={4}
                  value={resetPinForm.new_pin}
                  onChange={(e) => {
                    const val = e.target.value.replace(/[^0-9]/g, "");
                    setResetPinForm({
                      ...resetPinForm,
                      new_pin: val.slice(0, 4),
                    });
                  }}
                />
              </div>

              <div className="modal-field full">
                <label htmlFor="confirm-pin-modal">Confirm PIN</label>
                <input
                  id="confirm-pin-modal"
                  type="password"
                  inputMode="numeric"
                  maxLength={4}
                  value={resetPinForm.confirm_pin}
                  onChange={(e) => {
                    const val = e.target.value.replace(/[^0-9]/g, "");
                    setResetPinForm({
                      ...resetPinForm,
                      confirm_pin: val.slice(0, 4),
                    });
                  }}
                />
              </div>
            </div>

            <div className="modal-action-row">
              <button
                className="secondary-button"
                onClick={() => setResetPinUserId(null)}
              >
                Cancel
              </button>
              <button
                className="pay-button"
                onClick={handleResetPin}
              >
                Reset PIN
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
