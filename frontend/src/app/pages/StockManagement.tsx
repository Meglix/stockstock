"use client";

import { FormEvent, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Edit3, Plus, Search, Trash2, X } from "lucide-react";
import { DataPanel } from "../components/DataPanel";
import { StatusBadge } from "../components/StatusBadge";
import { useDemoStore } from "../context/DemoStoreContext";
import { StockHealth, StockItem, deriveStockStatus, stockStatusDescription } from "../data/inventory";
import { readCurrentUserLocation } from "../utils/userLocation";

type StockFormState = {
  productId: string;
  name: string;
  sku: string;
  category: string;
  supplier: string;
  current: string;
  recommended: string;
  reorderPoint: string;
  status: StockHealth;
  location: string;
};

const DEFAULT_STORE_LOCATION = "My Store";

function createEmptyForm(location = DEFAULT_STORE_LOCATION): StockFormState {
  return {
    productId: "",
    name: "",
    sku: "",
    category: "",
    supplier: "",
    current: "0",
    recommended: "",
    reorderPoint: "",
    status: "Critical",
    location,
  };
}

function toForm(item: StockItem): StockFormState {
  return {
    productId: item.productId,
    name: item.name,
    sku: item.sku,
    category: item.category,
    supplier: item.supplier,
    current: String(item.current),
    recommended: String(item.recommended),
    reorderPoint: String(item.reorderPoint),
    status: item.status,
    location: item.location,
  };
}

function productIdFromSku(sku: string) {
  return sku.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `custom-${Date.now()}`;
}

function isIntegerText(value: string, { allowZero = true } = {}) {
  if (!/^\d+$/.test(value.trim())) return false;
  const numericValue = Number(value);
  return Number.isInteger(numericValue) && (allowZero ? numericValue >= 0 : numericValue > 0);
}

function integerInput(value: string) {
  return value.replace(/\D/g, "");
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div className="form-field">
      <span>{label}</span>
      <div className="readonly-field">{value || "Not selected"}</div>
    </div>
  );
}

export function StockManagement() {
  const { products, stockItems, addStockItem, updateStockItem, deleteStockItem } = useDemoStore();
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<StockItem | null>(null);
  const [defaultStoreLocation] = useState(() => readCurrentUserLocation(DEFAULT_STORE_LOCATION));
  const [form, setForm] = useState<StockFormState>(() => createEmptyForm(defaultStoreLocation));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const derivedStatus = deriveStockStatus(Number(form.current || 0), Number(form.recommended || 1), Number(form.reorderPoint || 0));

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return stockItems.filter((item) => !term || item.name.toLowerCase().includes(term) || item.sku.toLowerCase().includes(term) || item.supplier.toLowerCase().includes(term));
  }, [search, stockItems]);
  const openAdd = () => {
    setEditingId(null);
    setForm(createEmptyForm(defaultStoreLocation));
    setErrors({});
    setFormOpen(true);
  };

  const openEdit = (item: StockItem) => {
    setEditingId(item.id);
    setForm(toForm(item));
    setErrors({});
    setFormOpen(true);
  };

  const closeForm = () => {
    setEditingId(null);
    setForm(createEmptyForm(defaultStoreLocation));
    setErrors({});
    setFormOpen(false);
  };

  const update = <K extends keyof StockFormState>(key: K, value: StockFormState[K]) => setForm((current) => ({ ...current, [key]: value }));

  const selectProduct = (productId: string) => {
    const product = products.find((item) => item.id === productId);
    if (!product) {
      setForm((current) => ({ ...createEmptyForm(defaultStoreLocation), current: current.current, productId }));
      return;
    }
    setForm((current) => ({
      ...current,
      productId: product.id,
      name: product.name,
      sku: product.sku,
      category: product.category,
      supplier: product.supplier,
      recommended: String(product.recommended ?? Math.max(product.stock, 1)),
      reorderPoint: String(product.reorderPoint ?? 0),
      status: deriveStockStatus(Number(current.current || 0), product.recommended ?? Math.max(product.stock, 1), product.reorderPoint ?? 0),
      location: current.location || product.location || defaultStoreLocation,
    }));
  };

  const validate = () => {
    const nextErrors: Record<string, string> = {};
    if (!form.productId) nextErrors.productId = "Select a catalog part.";
    if (form.productId && !form.name.trim()) nextErrors.name = "Product name is required.";
    if (form.productId && !form.sku.trim()) nextErrors.sku = "SKU is required.";
    if (form.productId && !form.category.trim()) nextErrors.category = "Category is required.";
    if (form.productId && !form.supplier.trim()) nextErrors.supplier = "Supplier is required.";
    if (!isIntegerText(form.current)) nextErrors.current = "Use a whole number, zero or above.";
    if (form.productId && !isIntegerText(form.recommended, { allowZero: false })) nextErrors.recommended = "Recommended quantity must be a whole number above 0.";
    if (form.productId && !isIntegerText(form.reorderPoint)) nextErrors.reorderPoint = "Use a whole number, zero or above.";
    if (isIntegerText(form.recommended, { allowZero: false }) && isIntegerText(form.reorderPoint) && Number(form.reorderPoint) > Number(form.recommended)) {
      nextErrors.reorderPoint = "Reorder point cannot exceed recommended quantity.";
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!validate()) return;

    const current = Number.parseInt(form.current, 10);
    const recommended = Number.parseInt(form.recommended, 10);
    const reorderPoint = Number.parseInt(form.reorderPoint, 10);
    const status = deriveStockStatus(current, recommended, reorderPoint);
    const payload = {
      productId: form.productId || productIdFromSku(form.sku),
      name: form.name.trim(),
      sku: form.sku.trim().toUpperCase(),
      category: form.category,
      supplier: form.supplier,
      current,
      recommended,
      reorderPoint,
      status,
      location: form.location.trim() || defaultStoreLocation,
    };

    setSaving(true);
    try {
      if (editingId) await updateStockItem(editingId, payload);
      else await addStockItem(payload);
      closeForm();
    } catch (error) {
      setErrors({ form: error instanceof Error ? error.message : "Stock save failed." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="space-y-5">
      <DataPanel
        title="Stock Management"
        eyebrow="Frontend demo CRUD"
        action={
          <button onClick={openAdd} className="primary-button min-h-10 px-3 py-2 text-sm">
            <Plus size={16} />
            Add Stock Item
          </button>
        }
      >
        <div className="mb-5 grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto]">
          <label className="control-shell">
            <Search size={16} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search stock item, SKU, supplier" />
          </label>
          <div className="panel-pill justify-center">{filtered.length} visible records</div>
        </div>

        <div className="overflow-hidden rounded-xl border border-white/[0.08]">
          <div className="overflow-x-auto">
            <table className="premium-table">
              <thead>
                <tr>
                  <th>Part</th>
                  <th>SKU</th>
                  <th>Category</th>
                  <th>Supplier</th>
                  <th>Current</th>
                  <th>Recommended</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item, index) => (
                  <motion.tr key={item.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.025 }}>
                    <td><span className="font-semibold text-white">{item.name}</span></td>
                    <td><span className="sku-chip">{item.sku}</span></td>
                    <td>{item.category}</td>
                    <td>{item.supplier}</td>
                    <td><span className="font-black text-orange-200">{item.current}</span></td>
                    <td>{item.recommended}</td>
                    <td><StatusBadge status={item.status} compact description={stockStatusDescription(item.status, item.current, item.recommended, item.reorderPoint)} /></td>
                    <td>
                      <div className="flex items-center gap-2">
                        <button onClick={() => openEdit(item)} className="icon-action" aria-label={`Edit ${item.name}`}><Edit3 size={15} /></button>
                        <button onClick={() => setDeleteTarget(item)} className="icon-action icon-action--danger" aria-label={`Delete ${item.name}`}><Trash2 size={15} /></button>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length === 0 ? <div className="px-5 py-12 text-center text-sm text-slate-500">No stock items match the current search.</div> : null}
        </div>
      </DataPanel>

      <AnimatePresence>
        {formOpen ? (
          <motion.div className="modal-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.form onSubmit={handleSubmit} initial={{ opacity: 0, y: 14, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 14, scale: 0.98 }} className="premium-modal premium-modal--wide">
              <div className="mb-5 flex items-start justify-between gap-4">
                <div>
                  <p className="panel-eyebrow">{editingId ? "Update record" : "Add record"}</p>
                  <h2 className="text-xl font-black text-white">{editingId ? "Update stock item" : "Add stock item"}</h2>
                </div>
                <button type="button" aria-label="Close form" onClick={closeForm} className="rounded-lg border border-white/[0.08] p-2 text-slate-400 transition hover:border-orange-300/25 hover:text-orange-200">
                  <X size={16} />
                </button>
              </div>

              {errors.form ? (
                <div className="mb-4 rounded-xl border border-red-300/20 bg-red-400/10 px-3 py-2 text-sm text-red-100">
                  {errors.form}
                </div>
              ) : null}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <label className="form-field sm:col-span-2">
                  <span>Catalog part</span>
                  <div className={`input-shell ${errors.productId ? "input-error" : ""}`}>
                    <select value={form.productId} onChange={(event) => selectProduct(event.target.value)} disabled={Boolean(editingId)}>
                      <option value="">Select from catalog</option>
                      {products.map((product) => (
                        <option key={product.id} value={product.id}>
                          {product.name} ({product.sku})
                        </option>
                      ))}
                    </select>
                  </div>
                  {errors.productId ? <small>{errors.productId}</small> : null}
                </label>
                <ReadOnlyField label="Product name" value={form.name} />
                <ReadOnlyField label="SKU" value={form.sku} />
                <ReadOnlyField label="Category" value={form.category} />
                <ReadOnlyField label="Supplier" value={form.supplier} />
                <label className="form-field"><span>Current quantity</span><div className={`input-shell ${errors.current ? "input-error" : ""}`}><input value={form.current} onChange={(event) => update("current", integerInput(event.target.value))} inputMode="numeric" pattern="[0-9]*" /></div>{errors.current ? <small>{errors.current}</small> : null}</label>
                <ReadOnlyField label="Recommended quantity" value={form.recommended} />
                <ReadOnlyField label="Reorder point" value={form.reorderPoint} />
                <div className="form-field">
                  <span>Status</span>
                  <div className="readonly-field">
                    <StatusBadge status={derivedStatus} compact description={stockStatusDescription(derivedStatus, Number(form.current || 0), Number(form.recommended || 1), Number(form.reorderPoint || 0))} />
                  </div>
                </div>
                <div className="sm:col-span-2">
                  <ReadOnlyField label="Location" value={form.location} />
                </div>
              </div>

              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <button type="button" className="secondary-action flex-1" onClick={closeForm}>Cancel</button>
                <button type="submit" className="primary-button flex-1" disabled={saving}>{saving ? "Saving..." : editingId ? "Update Stock Item" : "Add Stock Item"}</button>
              </div>
            </motion.form>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {deleteTarget ? (
          <motion.div className="modal-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.section initial={{ opacity: 0, y: 14, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 14, scale: 0.98 }} className="premium-modal">
              <div className="mb-4 rounded-xl border border-red-300/20 bg-red-400/10 p-3 text-red-200"><Trash2 size={20} /></div>
              <h2 className="text-xl font-black text-white">Delete stock item?</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">This removes {deleteTarget.name} from the local stock management view and marks it as order-only in the catalog.</p>
              <div className="mt-6 flex w-full flex-col gap-3 sm:flex-row">
                <button className="secondary-action flex-1" onClick={() => setDeleteTarget(null)}>Cancel</button>
                <button
                  className="danger-action flex-1"
                  onClick={async () => {
                    try {
                      await deleteStockItem(deleteTarget.id);
                      setDeleteTarget(null);
                    } catch {
                      setDeleteTarget(null);
                    }
                  }}
                >
                  Delete
                </button>
              </div>
            </motion.section>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}
