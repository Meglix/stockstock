"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { Activity, ArrowRight, BarChart3, Boxes, Gauge, Plus, ShieldCheck, Timer, TriangleAlert } from "lucide-react";
import { DataPanel } from "../components/DataPanel";
import { StatusBadge } from "../components/StatusBadge";
import { useDemoStore } from "../context/DemoStoreContext";
import { ClientOrder, StockHealth, stockStatusDescription } from "../data/inventory";

const stockTone: Record<StockHealth, string> = {
  Healthy: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  "Low Stock": "border-orange-400/30 bg-orange-400/10 text-orange-300",
  Critical: "border-red-400/30 bg-red-400/10 text-red-300",
  "Reorder Soon": "border-amber-300/25 bg-amber-300/10 text-amber-200",
  Overstock: "border-violet-300/25 bg-violet-300/10 text-violet-200",
};

const barTone: Record<StockHealth, string> = {
  Healthy: "bg-emerald-300/80",
  "Low Stock": "bg-orange-300/85",
  Critical: "bg-red-400/85",
  "Reorder Soon": "bg-amber-300/80",
  Overstock: "bg-violet-300/80",
};

function reservedQuantityByProduct(orders: ClientOrder[]) {
  const totals = new Map<string, number>();

  orders
    .filter((order) => order.status === "Approved" && order.fulfillmentStatus !== "fulfilled")
    .forEach((order) => {
      order.items.forEach((line) => {
        const reserved = line.allocatedQuantity ?? 0;
        if (reserved > 0) totals.set(line.productId, (totals.get(line.productId) ?? 0) + reserved);
      });
    });

  return totals;
}

export function Stock() {
  const { stockItems, clientOrders } = useDemoStore();
  const reservedByProduct = reservedQuantityByProduct(clientOrders);
  const overview = [
    { label: "Healthy Stock", value: stockItems.filter((item) => item.status === "Healthy").length, icon: ShieldCheck, status: "Healthy" as StockHealth, detail: "Stable reorder coverage" },
    { label: "Low Stock Items", value: stockItems.filter((item) => item.status === "Low Stock" || item.status === "Reorder Soon").length, icon: TriangleAlert, status: "Low Stock" as StockHealth, detail: "Restock within 7 days" },
    { label: "Critical Items", value: stockItems.filter((item) => item.status === "Critical").length, icon: Timer, status: "Critical" as StockHealth, detail: "Action required today" },
    { label: "Overstock Items", value: stockItems.filter((item) => item.status === "Overstock").length, icon: Boxes, status: "Overstock" as StockHealth, detail: "Reduce reorder volume" },
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="space-y-5">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <motion.article initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} whileHover={{ y: -3 }} className="premium-card xl:col-span-1">
          <div className="flex items-start justify-between gap-4">
            <div className="rounded-lg border border-orange-400/25 bg-orange-400/12 p-2.5 text-orange-200"><Plus size={20} /></div>
          </div>
          <p className="mt-5 text-sm font-bold text-white">Manage Stocks</p>
          <p className="mt-1 text-xs text-slate-500">Add, edit, delete, and tune inventory policies.</p>
          <Link href="/dashboard/stock/manage" className="secondary-action mt-5 w-full">
            Open
            <ArrowRight size={15} />
          </Link>
        </motion.article>

        {overview.map((item, index) => {
          const Icon = item.icon;
          return (
            <motion.article
              key={item.label}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: (index + 1) * 0.05 }}
              className="premium-card"
            >
              <div className="flex items-start justify-between gap-4">
                <div className={`rounded-lg border p-2.5 ${stockTone[item.status]}`}><Icon size={20} /></div>
                <span className="text-3xl font-black text-white">{item.value}</span>
              </div>
              <p className="mt-5 text-sm font-bold text-white">{item.label}</p>
              <p className="mt-1 text-xs text-slate-500">{item.detail}</p>
            </motion.article>
          );
        })}
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <DataPanel title="Current Stock vs Recommended Stock" eyebrow="Inventory health" action={<span className="panel-pill"><BarChart3 size={13} /> Target view</span>}>
          {stockItems.length ? (
            <div className="space-y-5">
              {stockItems.map((item, index) => {
                const target = Math.max(item.recommended, item.reorderPoint, 1);
                const reserved = reservedByProduct.get(item.productId) ?? 0;
                const onHand = item.current + reserved;
                const currentPct = item.current <= 0 ? 0 : Math.min(100, Math.round((item.current / target) * 100));
                const recommendedPct = 100;
                return (
                  <motion.div key={item.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.04 }}>
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <div>
                        <p className="font-bold text-white">{item.category}</p>
                        <p className="text-xs text-slate-500">
                          Available {item.current} / Target {target}
                          {reserved > 0 ? <span className="text-orange-200"> / Reserved {reserved} / On hand {onHand}</span> : null}
                        </p>
                      </div>
                      <StatusBadge status={item.status} description={stockStatusDescription(item.status, item.current, item.recommended, item.reorderPoint, reserved)} />
                    </div>
                    <div className="space-y-2">
                      <div className="h-2.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <motion.div initial={{ width: 0 }} animate={{ width: `${currentPct}%` }} transition={{ duration: 0.75 }} className={`h-full rounded-full ${barTone[item.status]}`} />
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.05]">
                        <motion.div initial={{ width: 0 }} animate={{ width: `${recommendedPct}%` }} transition={{ duration: 0.75, delay: 0.08 }} className="h-full rounded-full bg-slate-300/35" />
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-xl border border-white/[0.08] bg-white/[0.025] px-5 py-12 text-center text-sm text-slate-500">
              No local stock has been added yet. Use Manage Stocks to add your current quantity for a catalog part.
            </div>
          )}
        </DataPanel>

        <DataPanel title="Category Health" eyebrow="Priority list" action={<span className="panel-pill"><Activity size={13} /> {stockItems.length} items</span>}>
          {stockItems.length ? (
            <div className="space-y-3">
              {stockItems.map((item, index) => {
                const reserved = reservedByProduct.get(item.productId) ?? 0;
                const target = Math.max(item.recommended, item.reorderPoint, 1);
                return (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.04 }}
                    className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.08] bg-white/[0.035] p-4"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.08] bg-black/20 text-orange-200"><Gauge size={16} /></div>
                      <div className="min-w-0">
                        <p className="truncate font-bold text-white">{item.name}</p>
                        <p className="text-xs text-slate-500">
                          Coverage {Math.round((item.current / target) * 100)}%
                          {reserved > 0 ? ` / ${reserved} reserved` : ""}
                        </p>
                      </div>
                    </div>
                    <StatusBadge status={item.status} compact description={stockStatusDescription(item.status, item.current, item.recommended, item.reorderPoint, reserved)} />
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-xl border border-white/[0.08] bg-white/[0.025] px-5 py-12 text-center text-sm text-slate-500">
              Your store stock list is empty.
            </div>
          )}
        </DataPanel>
      </section>
    </motion.div>
  );
}
