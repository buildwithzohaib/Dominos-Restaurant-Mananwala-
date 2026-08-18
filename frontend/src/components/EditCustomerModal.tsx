import { X } from "lucide-react";
import { useState } from "react";
import { api } from "../services/api";
import type { CustomerSearchResult } from "../types";

export function EditCustomerModal({
  customer,
  onClose,
  onSaved,
}: {
  customer: CustomerSearchResult;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(customer.name_display);
  const [phone, setPhone] = useState(customer.phone_raw || "");
  const [address, setAddress] = useState(customer.address || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSave() {
    if (!name.trim()) {
      setError("Customer name is required");
      return;
    }

    setBusy(true);
    setError("");

    try {
      await api.updateCustomer(customer.id, {
        name: name.trim(),
        phone: phone.trim() || undefined,
        address: address.trim() || undefined,
      });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update customer");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="inventory-modal">
        <button className="modal-close" onClick={onClose}>
          <X />
        </button>

        <p className="eyebrow">CUSTOMERS</p>
        <h2>Edit Customer</h2>

        <div className="modal-field-grid">
          <label className="modal-field">
            Name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Customer name"
              disabled={busy}
            />
          </label>

          <label className="modal-field">
            Phone
            <input
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="Phone number (optional)"
              disabled={busy}
            />
          </label>

          <label className="modal-field">
            Address
            <textarea
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Delivery address (optional)"
              rows={3}
              disabled={busy}
            />
          </label>
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="modal-action-row">
          <button
            className="secondary-button"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            className="pay-button"
            onClick={handleSave}
            disabled={busy || !name.trim()}
          >
            {busy ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
