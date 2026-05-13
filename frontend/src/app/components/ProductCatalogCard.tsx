"use client";

import { motion } from "motion/react";
import {
  AirVent,
  BatteryCharging,
  CircleDot,
  CircuitBoard,
  Cog,
  Disc3,
  Droplets,
  Eye,
  Filter,
  Lightbulb,
  Package,
  ShoppingCart,
  Snowflake,
  Sparkles,
  SprayCan,
  Wind,
  Wrench,
} from "lucide-react";
import { CatalogProduct, stockStatusDescription } from "../data/inventory";
import { StatusBadge } from "./StatusBadge";

const categoryIcon: Record<string, typeof Package> = {
  "AC Cooling": AirVent,
  Accessories: Sparkles,
  Battery: BatteryCharging,
  Batteries: BatteryCharging,
  Brakes: Disc3,
  Consumables: SprayCan,
  Coolant: Droplets,
  Electronics: CircuitBoard,
  Filters: Filter,
  Fluids: Droplets,
  "Engine Parts": Cog,
  Lighting: Lightbulb,
  Maintenance: Wrench,
  Tires: CircleDot,
  "Winter Fluids": Snowflake,
  Wipers: Wind,
};

export function ProductCatalogCard({ product, index, onView, onOrder }: { product: CatalogProduct; index: number; onView: () => void; onOrder: () => void }) {
  const Icon = categoryIcon[product.category] ?? Package;
  const disabled = product.availability === "order-only";
  const statusDescription = stockStatusDescription(product.status, product.stock, product.recommended ?? Math.max(product.stock, 1), product.reorderPoint ?? 0);

  return (
    <motion.article
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.035 }}
      whileHover={{ y: disabled ? -1 : -4 }}
      className={`product-card ${disabled ? "product-card--disabled" : ""}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl border ${disabled ? "border-white/[0.08] bg-white/[0.035] text-slate-500" : "border-orange-300/22 bg-orange-400/12 text-orange-200"}`}>
          <Icon size={20} />
        </div>
        <StatusBadge status={product.status} compact description={statusDescription} />
      </div>

      <div className="mt-5 min-h-[98px]">
        <p className="line-clamp-2 text-base font-black leading-snug text-white">{product.name}</p>
        <p className="mt-2"><span className="sku-chip">{product.sku}</span></p>
        <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
          <div>
            <p className="text-slate-500">Category</p>
            <p className={`mt-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-1 font-semibold ${disabled ? "border-white/[0.08] bg-white/[0.035] text-slate-400" : "border-orange-300/20 bg-orange-400/10 text-orange-100"}`}>
              <Icon size={12} />
              {product.category}
            </p>
          </div>
          <div>
            <p className="text-slate-500">Supplier</p>
            <p className="mt-1 font-semibold text-slate-300">{product.supplier}</p>
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-end justify-between gap-3 border-t border-white/[0.07] pt-4">
        <div>
          <p className="text-xs text-slate-500">Stock</p>
          <p className={`mt-1 text-2xl font-black ${disabled ? "text-slate-500" : "text-orange-200"}`}>{disabled ? "Order" : product.stock}</p>
          {disabled ? <p className="mt-1 text-[0.68rem] font-bold uppercase text-slate-500">Supplier only</p> : null}
        </div>
        <button onClick={disabled ? onOrder : onView} className={disabled ? "secondary-action" : "primary-button min-h-10 px-3 py-2 text-sm"}>
          {disabled ? <ShoppingCart size={15} /> : <Eye size={15} />}
          {disabled ? "Add to Supplier Order" : "View"}
        </button>
      </div>
    </motion.article>
  );
}
