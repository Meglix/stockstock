"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { Filter, PackagePlus, Search, SlidersHorizontal, X } from "lucide-react";
import { DataPanel } from "../components/DataPanel";
import { ProductCatalogCard } from "../components/ProductCatalogCard";
import { StatusBadge } from "../components/StatusBadge";
import { useDemoStore } from "../context/DemoStoreContext";
import { CatalogProduct, PartStatus } from "../data/inventory";

type AvailabilityFilter = "All" | "available" | "order-only";

const availabilityLabels: Record<AvailabilityFilter, string> = {
  All: "Any",
  available: "Available locally",
  "order-only": "Order only",
};

function removeFromList(values: string[], value: string) {
  return values.filter((item) => item !== value);
}

export function Parts() {
  const router = useRouter();
  const params = useSearchParams();
  const { products } = useDemoStore();
  const [search, setSearch] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [supplier, setSupplier] = useState("All");
  const [status, setStatus] = useState<PartStatus | "All">("All");
  const [availability, setAvailability] = useState<AvailabilityFilter>("All");
  const [selected, setSelected] = useState<CatalogProduct | null>(null);
  const [queryApplied, setQueryApplied] = useState(false);

  const categories = useMemo(() => Array.from(new Set(products.map((part) => part.category))).sort(), [products]);
  const suppliers = useMemo(() => ["All", ...Array.from(new Set(products.map((part) => part.supplier))).sort()], [products]);
  const statuses = useMemo<Array<PartStatus | "All">>(() => ["All", "In Stock", "Low Stock", "Critical", "Overstock", "Order Only"], []);

  useEffect(() => {
    if (queryApplied) return;
    if (params.get("availability") === "available") setAvailability("available");
    setQueryApplied(true);
  }, [params, queryApplied]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return products.filter((part) => {
      const matchesSearch =
        !term ||
        part.name.toLowerCase().includes(term) ||
        part.sku.toLowerCase().includes(term) ||
        part.category.toLowerCase().includes(term) ||
        part.supplier.toLowerCase().includes(term);
      const matchesCategory = selectedCategories.length === 0 || selectedCategories.includes(part.category);
      const matchesAvailability = availability === "All" || part.availability === availability;
      return matchesSearch && matchesCategory && (supplier === "All" || part.supplier === supplier) && (status === "All" || part.status === status) && matchesAvailability;
    });
  }, [availability, products, search, selectedCategories, status, supplier]);

  const activeFilters = [
    ...selectedCategories.map((category) => ({ key: `category-${category}`, label: category, onRemove: () => setSelectedCategories((current) => removeFromList(current, category)) })),
    supplier !== "All" ? { key: "supplier", label: supplier, onRemove: () => setSupplier("All") } : null,
    status !== "All" ? { key: "status", label: status, onRemove: () => setStatus("All") } : null,
    availability !== "All" ? { key: "availability", label: availabilityLabels[availability], onRemove: () => setAvailability("All") } : null,
    search.trim() ? { key: "search", label: `Search: ${search.trim()}`, onRemove: () => setSearch("") } : null,
  ].filter((item): item is { key: string; label: string; onRemove: () => void } => Boolean(item));

  const clearFilters = () => {
    setSearch("");
    setSelectedCategories([]);
    setSupplier("All");
    setStatus("All");
    setAvailability("All");
  };

  const toggleCategory = (category: string) => {
    setSelectedCategories((current) => (current.includes(category) ? removeFromList(current, category) : [...current, category]));
  };

  const openSupplierOrder = (product: CatalogProduct) => {
    router.push(`/dashboard/orders?tab=suppliers&supplier=${encodeURIComponent(product.supplier)}&product=${encodeURIComponent(product.id)}`);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="space-y-5">
      <DataPanel title="Parts Catalog" eyebrow="Local and supplier-order catalog" action={<span className="panel-pill"><PackagePlus size={13} /> {filtered.length} products</span>}>
        <div className="mb-5 grid grid-cols-1 gap-3 xl:grid-cols-[1.25fr_0.75fr_0.75fr_0.75fr]">
          <label className="filter-control">
            <span>Search</span>
            <div className="control-shell">
              <Search size={16} />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Product, SKU, supplier" />
            </div>
          </label>
          <label className="filter-control">
            <span>Supplier</span>
            <div className="control-shell">
              <SlidersHorizontal size={16} />
              <select value={supplier} onChange={(event) => setSupplier(event.target.value)}>
                {suppliers.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
          </label>
          <label className="filter-control">
            <span>Status</span>
            <div className="control-shell">
              <span className="h-2 w-2 rounded-full bg-orange-300" />
              <select value={status} onChange={(event) => setStatus(event.target.value as PartStatus | "All")}>
                {statuses.map((item) => <option key={item}>{item}</option>)}
              </select>
            </div>
          </label>
          <label className="filter-control">
            <span>Availability</span>
            <div className="control-shell">
              <Filter size={16} />
              <select value={availability} onChange={(event) => setAvailability(event.target.value as AvailabilityFilter)}>
                {Object.entries(availabilityLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </label>
        </div>

        <div className="mb-5 rounded-xl border border-white/[0.08] bg-white/[0.025] p-3">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-white">Categories</p>
              <p className="mt-1 text-xs text-slate-500">Select one or more product groups.</p>
            </div>
            {selectedCategories.length ? (
              <button type="button" className="secondary-action min-h-9 px-3 py-1.5 text-xs" onClick={() => setSelectedCategories([])}>
                Clear categories
              </button>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {categories.map((category) => {
              const active = selectedCategories.includes(category);
              return (
                <button key={category} type="button" onClick={() => toggleCategory(category)} className={`filter-chip ${active ? "filter-chip--active" : ""}`}>
                  <span className={`h-2 w-2 rounded-full ${active ? "bg-orange-200" : "bg-slate-600"}`} />
                  {category}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mb-5 flex flex-wrap items-center gap-2">
          {activeFilters.length ? (
            <>
              {activeFilters.map((filter) => (
                <button key={filter.key} type="button" onClick={filter.onRemove} className="active-filter-chip">
                  {filter.label}
                  <X size={13} />
                </button>
              ))}
              <button type="button" onClick={clearFilters} className="secondary-action min-h-9 px-3 py-1.5 text-xs">
                Clear filters
              </button>
            </>
          ) : (
            <span className="text-sm text-slate-500">Showing all {products.length} products. Search or select filters to narrow the catalog.</span>
          )}
        </div>

        <div className="catalog-grid">
          {filtered.map((part, index) => (
            <ProductCatalogCard key={part.id} product={part} index={index} onView={() => setSelected(part)} onOrder={() => openSupplierOrder(part)} />
          ))}
        </div>
        {filtered.length === 0 ? <div className="px-5 py-12 text-center text-sm text-slate-500">No parts match the current filters.</div> : null}
      </DataPanel>

      <AnimatePresence>
        {selected ? (
          <motion.div className="modal-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.section initial={{ opacity: 0, y: 14, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 14, scale: 0.98 }} className="premium-modal">
              <div className="mb-5 flex items-start justify-between gap-4">
                <div>
                  <p className="panel-eyebrow">Product details</p>
                  <h2 className="text-xl font-black text-white">{selected.name}</h2>
                </div>
                <button aria-label="Close product details" onClick={() => setSelected(null)} className="rounded-lg border border-white/[0.08] p-2 text-slate-400 transition hover:border-orange-300/25 hover:text-orange-200">
                  <X size={16} />
                </button>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="detail-tile"><span>SKU</span><strong>{selected.sku}</strong></div>
                <div className="detail-tile"><span>Category</span><strong>{selected.category}</strong></div>
                <div className="detail-tile"><span>Supplier</span><strong>{selected.supplier}</strong></div>
                <div className="detail-tile"><span>Stock</span><strong>{selected.availability === "order-only" ? "Order only" : selected.stock}</strong></div>
              </div>

              <div className="mt-5 flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-white/[0.035] p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-bold text-white">Availability</p>
                  <p className="mt-1 text-sm text-slate-500">{selected.availability === "order-only" ? "Not available locally. Add it to a supplier order." : "Available in the local RRParts store."}</p>
                </div>
                <StatusBadge status={selected.status} />
              </div>

              <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                <button className="secondary-action flex-1" onClick={() => setSelected(null)}>Close</button>
                <button className="primary-button flex-1" onClick={() => openSupplierOrder(selected)}>
                  {selected.availability === "order-only" ? "Add to Supplier Order" : "Order More"}
                  <PackagePlus size={16} />
                </button>
              </div>
            </motion.section>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}
