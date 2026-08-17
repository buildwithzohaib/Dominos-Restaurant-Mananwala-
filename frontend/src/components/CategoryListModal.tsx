import { X, Edit2, Power, PowerOff } from "lucide-react";
import { useState, useMemo } from "react";
import { useCatalog } from "../context/CatalogContext";
import { api } from "../services/api";
import type { Category } from "../types";

export function CategoryListModal({ onClose }: { onClose: () => void }) {
  const { allCategories, allProducts, refresh, isLoading } = useCatalog();
  const [newCategoryName, setNewCategoryName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Inline edit state: tracks which category is being renamed and its temp value
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState("");

  // Deactivate warning state: tracks which category is awaiting confirmation
  const [confirmDeactivateId, setConfirmDeactivateId] = useState<number | null>(null);

  // Calculate product counts per category
  const categoryCounts = useMemo(() => {
    const counts = new Map<number, { total: number; active: number }>();

    allCategories.forEach((cat) => {
      counts.set(cat.id, { total: 0, active: 0 });
    });

    allProducts.forEach((prod) => {
      const current = counts.get(prod.category_id);
      if (current) {
        current.total += 1;
        if (prod.available) {
          current.active += 1;
        }
      }
    });

    return counts;
  }, [allCategories, allProducts]);

  async function createCategory() {
    const trimmed = newCategoryName.trim();
    if (!trimmed) {
      setError("Category name cannot be empty");
      return;
    }

    setBusy(true);
    setError("");
    try {
      await api.createCategory(trimmed);
      setNewCategoryName("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create category");
    } finally {
      setBusy(false);
    }
  }

  async function startRename(cat: Category) {
    setEditingId(cat.id);
    setEditingName(cat.name_display);
  }

  async function saveRename(id: number) {
    const trimmed = editingName.trim();
    if (!trimmed) {
      setError("Category name cannot be empty");
      return;
    }

    setBusy(true);
    setError("");
    try {
      await api.updateCategory(id, trimmed);
      setEditingId(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not rename category");
    } finally {
      setBusy(false);
    }
  }

  function cancelRename() {
    setEditingId(null);
    setEditingName("");
  }

  function startDeactivateConfirm(id: number) {
    setConfirmDeactivateId(id);
  }

  async function confirmDeactivate(id: number) {
    setBusy(true);
    setError("");
    try {
      await api.deactivateCategory(id);
      setConfirmDeactivateId(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not deactivate category");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActivate(cat: Category) {
    if (cat.active) {
      // Deactivating — show warning
      startDeactivateConfirm(cat.id);
    } else {
      // Activating — no warning needed
      setBusy(true);
      setError("");
      try {
        await api.activateCategory(cat.id);
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not activate category");
      } finally {
        setBusy(false);
      }
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="inventory-modal">
        <button className="modal-close" onClick={onClose} disabled={busy}>
          <X />
        </button>

        <p className="eyebrow">CATALOG</p>
        <h2>Manage Categories</h2>

        {error && <div className="error-box">{error}</div>}

        {/* Categories list */}
        {isLoading ? (
          <div className="loading">Loading categories...</div>
        ) : allCategories.length === 0 ? (
          <div className="loading">No categories.</div>
        ) : (
          <div className="category-list">
            {/* Create category row */}
            <div className="category-list-create">
              <input
                type="text"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                placeholder="New category name"
                disabled={busy || isLoading}
                onKeyDown={(e) => {
                  if (e.key === "Enter") createCategory();
                }}
              />
              <button
                onClick={createCategory}
                disabled={busy || isLoading || !newCategoryName.trim()}
                className="add-stock-button"
              >
                Add
              </button>
            </div>

            {/* Header */}
            <div className="category-list-head">
              <span>Category</span>
              <span>Products</span>
              <span />
            </div>

            {/* List items */}
            {allCategories.map((cat) => {
              const counts = categoryCounts.get(cat.id) || { total: 0, active: 0 };
              const isEditing = editingId === cat.id;
              const isConfirming = confirmDeactivateId === cat.id;

              return (
                <div
                  key={cat.id}
                  className={`category-list-row ${!cat.active ? "disabled-row" : ""}`}
                >
                  {/* Name column — inline edit or display */}
                  <span className="item-name">
                    {isEditing ? (
                      <input
                        type="text"
                        autoFocus
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        disabled={busy}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveRename(cat.id);
                          if (e.key === "Escape") cancelRename();
                        }}
                      />
                    ) : (
                      cat.name_display
                    )}
                  </span>

                  {/* Product count column */}
                  <span className="count">
                    {counts.active} / {counts.total}
                  </span>

                  {/* Action buttons or inline controls */}
                  <span className="row-actions">
                    {isEditing ? (
                      <>
                        <button
                          className="row-action-button"
                          onClick={() => saveRename(cat.id)}
                          disabled={busy}
                          title="Save"
                        >
                          ✓
                        </button>
                        <button
                          className="row-action-button"
                          onClick={cancelRename}
                          disabled={busy}
                          title="Cancel"
                        >
                          ✕
                        </button>
                      </>
                    ) : !isConfirming && (
                      <>
                        <button
                          className="row-action-button"
                          onClick={() => startRename(cat)}
                          disabled={busy}
                          title="Rename"
                        >
                          <Edit2 size={16} />
                        </button>
                        <button
                          className="row-action-button"
                          onClick={() => toggleActivate(cat)}
                          disabled={busy}
                          title={cat.active ? "Deactivate" : "Activate"}
                        >
                          {cat.active ? (
                            <Power size={16} />
                          ) : (
                            <PowerOff size={16} />
                          )}
                        </button>
                      </>
                    )}
                  </span>

                  {/* Deactivation warning with action buttons — shown below the row */}
                  {isConfirming && (
                    <div className="category-list-warning">
                      <div>
                        <strong>{cat.name_display}</strong> has {counts.total}{" "}
                        {counts.total === 1 ? "product" : "products"},{" "}
                        {counts.active} of them currently on the POS menu. Deactivating
                        hides them from the POS. Continue?
                      </div>
                      <div className="modal-action-row category-list-warning-actions">
                        <button
                          className="secondary-button"
                          onClick={() => setConfirmDeactivateId(null)}
                          disabled={busy}
                        >
                          Cancel
                        </button>
                        <button
                          className="pay-button danger"
                          onClick={() => confirmDeactivate(cat.id)}
                          disabled={busy}
                        >
                          {busy ? "Deactivating..." : "Deactivate"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
