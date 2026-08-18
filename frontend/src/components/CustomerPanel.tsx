import { useState, useCallback, useEffect } from "react";
import { usePOS } from "../context/POSContext";
import { SettingsContext } from "../context/SettingsContext";
import { api } from "../services/api";
import type { Customer, CustomerSearchResult } from "../types";
import { X, Loader } from "lucide-react";
import { paisaToRupees } from "../utils/money";
import { useContext } from "react";

export function CustomerPanel() {
  const { state, setCustomer, setDeliveryAddress, setDeliveryCharge } = usePOS();
  const settingsContext = useContext(SettingsContext);
  const settings = settingsContext?.settings;

  // Search state
  const [searchText, setSearchText] = useState("");
  const [searchResults, setSearchResults] = useState<CustomerSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState("");

  // Create form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createPhone, setCreatePhone] = useState("");
  const [createError, setCreateError] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (searchText.trim().length < 2) {
        setSearchResults([]);
        return;
      }

      setIsSearching(true);
      setSearchError("");
      try {
        const results = await api.searchCustomers(searchText);
        setSearchResults(results);
      } catch (e) {
        setSearchError(
          e instanceof Error ? e.message : "Search failed"
        );
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 600);

    return () => clearTimeout(timer);
  }, [searchText]);

  const handleSelectCustomer = useCallback(
    (customer: CustomerSearchResult) => {
      setCustomer(customer as unknown as Customer);
      setSearchText("");
      setSearchResults([]);
      setShowCreateForm(false);

      // Phase 3.5: Prefill delivery address if customer selected AND orderType is DELIVERY
      // AND the address field is currently empty (don't overwrite what was already typed)
      if (state.orderType === "DELIVERY" && state.deliveryAddress.trim() === "" && customer.address) {
        setDeliveryAddress(customer.address);
      }
    },
    [setCustomer, setDeliveryAddress, state.orderType, state.deliveryAddress]
  );

  const extractDigits = (text: string): string => {
    return text.replace(/\D/g, "");
  };

  const handleShowCreateForm = useCallback(() => {
    const digits = extractDigits(searchText);
    const hasOnlyDigits = digits.length > 0 && extractDigits(searchText) === searchText.trim();

    if (hasOnlyDigits) {
      setCreatePhone(searchText.trim());
      setCreateName("");
    } else {
      setCreateName(searchText.trim());
      setCreatePhone("");
    }

    setShowCreateForm(true);
  }, [searchText]);

  const handleCreateCustomer = async () => {
    const trimmedName = createName.trim();
    if (!trimmedName) {
      setCreateError("Customer name is required");
      return;
    }

    setIsCreating(true);
    setCreateError("");

    try {
      const newCustomer = await api.createCustomer({
        name: trimmedName,
        phone: createPhone.trim() || undefined,
      });

      handleSelectCustomer(newCustomer as unknown as CustomerSearchResult);
    } catch (e) {
      setCreateError(
        e instanceof Error ? e.message : "Could not create customer"
      );
    } finally {
      setIsCreating(false);
    }
  };

  const handleClearCustomer = useCallback(() => {
    setCustomer(null);
    setDeliveryAddress("");
  }, [setCustomer, setDeliveryAddress]);

  // Default state: search input
  if (!state.selectedCustomer) {
    return (
      <div className="customer-panel">
        <div className="search-box">
          <input
            type="text"
            placeholder="Customer phone or name"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            autoFocus
          />
          {isSearching && <Loader size={16} className="spinner" />}
        </div>

        {searchError && (
          <div className="error-box" style={{ marginTop: "8px" }}>
            {searchError}
          </div>
        )}

        {/* Results list */}
        {searchText.trim().length >= 2 && (
          <div className="customer-results">
            {searchResults.length > 0 ? (
              <ul>
                {searchResults.map((customer) => (
                  <li key={customer.id}>
                    <button
                      className="result-item"
                      onClick={() => handleSelectCustomer(customer)}
                    >
                      <div className="result-name">
                        {customer.name_display}
                      </div>
                      {customer.phone_raw && (
                        <div className="result-phone">
                          {customer.phone_raw}
                        </div>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            ) : !isSearching ? (
              <button
                className="no-match-item"
                onClick={handleShowCreateForm}
              >
                No match — Add new customer
              </button>
            ) : null}
          </div>
        )}

        {/* Create form */}
        {showCreateForm && (
          <div className="create-form">
            <div className="modal-field full">
              <label>Name (required)</label>
              <input
                type="text"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="Customer name"
                autoFocus={!createName}
              />
            </div>

            <div className="modal-field full">
              <label>Phone</label>
              <input
                type="text"
                value={createPhone}
                onChange={(e) => setCreatePhone(e.target.value)}
                placeholder="Phone number (optional)"
              />
            </div>

            {createError && (
              <div className="error-box">
                {createError}
              </div>
            )}

            <div className="create-actions">
              <button
                className="secondary-button"
                onClick={() => setShowCreateForm(false)}
                disabled={isCreating}
              >
                Cancel
              </button>

              <button
                className="pay-button"
                onClick={handleCreateCustomer}
                disabled={isCreating || !createName.trim()}
              >
                {isCreating ? "Creating..." : "Save & Select"}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Selected state: chip + optional address field
  return (
    <div className="customer-panel">
      <div className="customer-chip">
        <div className="chip-info">
          <div className="chip-name">
            {state.selectedCustomer.name_display}
          </div>
          {state.selectedCustomer.phone_raw && (
            <div className="chip-phone">
              {state.selectedCustomer.phone_raw}
            </div>
          )}
        </div>
        <button
          className="chip-close"
          onClick={handleClearCustomer}
          title="Remove customer"
        >
          <X size={16} />
        </button>
      </div>

      {/* Delivery address for DELIVERY orders */}
      {state.orderType === "DELIVERY" && (
        <>
          <div className="modal-field full">
            <label>Delivery Address</label>
            <textarea
              value={state.deliveryAddress}
              onChange={(e) => setDeliveryAddress(e.target.value)}
              placeholder="Enter delivery address"
              rows={3}
            />
          </div>

          <div className="modal-field full">
            <label>Delivery Charge</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={state.deliveryChargeText}
              onChange={(e) => setDeliveryCharge(e.target.value)}
              placeholder="0"
            />
          </div>
        </>
      )}
    </div>
  );
}
