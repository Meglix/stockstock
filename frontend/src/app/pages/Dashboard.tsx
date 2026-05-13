"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { AlertTriangle, ArrowRight, Boxes, BrainCircuit, LayoutGrid, MapPin, Newspaper, Package, ShoppingCart } from "lucide-react";
import { DataPanel } from "../components/DataPanel";
import { DemandForecastChart } from "../components/DemandForecastChart";
import { KpiCard } from "../components/KpiCard";
import { StatusBadge } from "../components/StatusBadge";
import { SupplierMap } from "../components/SupplierMap";
import { useDemoStore } from "../context/DemoStoreContext";
import { ForecastHorizon, getForecastSeries } from "../data/forecasting";
import { marketTrends } from "../data/inventory";

const trendTone: Record<string, string> = {
  High: "border-orange-300/25 bg-orange-400/12 text-orange-200",
  Medium: "border-sky-300/20 bg-sky-400/10 text-sky-200",
  Stable: "border-emerald-300/20 bg-emerald-400/10 text-emerald-200",
  Declining: "border-red-300/25 bg-red-400/12 text-red-200",
};

export function Dashboard() {
  const router = useRouter();
  const [forecastHorizon, setForecastHorizon] = useState<ForecastHorizon>(14);
  const { products, stockItems, clientOrders, supplierOrders, dashboardSummary } = useDemoStore();
  const totalAvailable = dashboardSummary?.kpis.total_available_parts ?? products.filter((product) => product.availability === "available").reduce((sum, product) => sum + product.stock, 0);
  const categories = dashboardSummary?.kpis.categories ?? new Set(products.map((product) => product.category)).size;
  const pendingClients = dashboardSummary?.kpis.pending_client_orders ?? clientOrders.filter((order) => order.status === "Pending" || order.status === "Scheduled").length;
  const pendingSuppliers = dashboardSummary?.kpis.pending_supplier_orders ?? supplierOrders.filter((order) => order.status === "Pending" || order.status === "Delivered").length;
  const criticalStock = dashboardSummary?.kpis.critical_stock_alerts ?? stockItems.filter((item) => item.status === "Critical" || item.status === "Low Stock").length;
  const priorityItems = dashboardSummary?.priority_stock.length ? dashboardSummary.priority_stock : [...stockItems]
    .filter((item) => item.status === "Critical" || item.status === "Low Stock" || item.status === "Reorder Soon")
    .sort((a, b) => a.current - b.current)
    .slice(0, 5);
  const trendItems = dashboardSummary?.market_trends.length ? dashboardSummary.market_trends : marketTrends;
  const supplierLocations = dashboardSummary?.supplier_locations ?? [];
  const forecastPoints = useMemo(
    () =>
      getForecastSeries({
        locationId: "RO_BUC",
        category: "Tires",
        sku: "PEU-WINTER-TIRE-205",
        horizon: forecastHorizon,
      }),
    [forecastHorizon],
  );

  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="space-y-6">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Total Available Parts" value={totalAvailable.toLocaleString()} detail="Live demo stock across local catalog" icon={Package} tone="orange" index={0} href="/dashboard/parts?availability=available" />
        <KpiCard label="Categories" value={categories} detail="Active product groups in catalog" icon={LayoutGrid} tone="steel" index={1} href="/dashboard/parts?focus=categories" />

        <motion.article
          role="button"
          tabIndex={0}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.11, duration: 0.35 }}
          whileHover={{ y: -3 }}
          onClick={() => router.push("/dashboard/orders?tab=clients&group=needs-review")}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") router.push("/dashboard/orders?tab=clients&group=needs-review");
          }}
          className="premium-card premium-card--clickable group cursor-pointer"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="rounded-lg border border-orange-400/25 bg-gradient-to-br from-orange-500/20 to-orange-500/5 p-2.5 text-orange-300">
              <ShoppingCart size={20} />
            </div>
            <span className="text-xs font-semibold uppercase text-slate-500">Pending</span>
          </div>
          <p className="mt-5 text-sm text-slate-400">Pending Orders</p>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-white/[0.08] bg-white/[0.035] p-3">
              <p className="text-2xl font-black text-white">{pendingClients}</p>
              <p className="mt-1 text-xs text-slate-500">From clients</p>
            </div>
            <div className="rounded-xl border border-white/[0.08] bg-white/[0.035] p-3">
              <p className="text-2xl font-black text-white">{pendingSuppliers}</p>
              <p className="mt-1 text-xs text-slate-500">To suppliers</p>
            </div>
          </div>
        </motion.article>

        <KpiCard label="Critical Stock Alerts" value={criticalStock} detail="Low or critical items needing action" icon={AlertTriangle} tone="red" index={3} href="/dashboard/stock" />
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[1.25fr_0.75fr]">
        <DataPanel title="Demand Forecast Outlook" eyebrow="Actual vs forecast demand" action={<span className="panel-pill"><BrainCircuit size={13} /> ML horizon</span>}>
          <DemandForecastChart points={forecastPoints} horizon={forecastHorizon} onHorizonChange={setForecastHorizon} compact />
        </DataPanel>

        <DataPanel title="Sales Demand Signals" eyebrow="Order and sales movement" action={<span className="panel-pill"><Newspaper size={13} /> {trendItems.length} signals</span>}>
          <div className="space-y-3">
            {trendItems.map((trend, index) => (
              <motion.article
                key={trend.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className="rounded-xl border border-white/[0.08] bg-white/[0.035] p-4"
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${trendTone[trend.priority]}`}>{trend.priority}</span>
                  <span className="rounded-full border border-white/[0.08] px-2.5 py-1 text-xs font-semibold text-slate-400">{trend.category}</span>
                </div>
                <p className="font-bold text-white">{trend.title}</p>
                <p className="mt-2 text-sm leading-5 text-slate-500">{trend.detail}</p>
              </motion.article>
            ))}
          </div>
        </DataPanel>
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_0.72fr]">
        <DataPanel title="Supplier World Map" eyebrow="Global network" action={<span className="panel-pill"><MapPin size={13} /> {(supplierLocations.length || 5)} supplier locations</span>}>
          <SupplierMap locations={supplierLocations} />
        </DataPanel>

        <DataPanel title="Stock Priority / Critical Stock Alerts" eyebrow="Manager action list" action={<span className="panel-pill"><Boxes size={13} /> Priority</span>}>
          <div className="space-y-3">
            {priorityItems.map((item, index) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.08] bg-white/[0.035] p-4"
              >
                <div className="min-w-0">
                  <p className="truncate font-bold text-white">{item.name}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.current} left / recommended {item.recommended}</p>
                </div>
                <StatusBadge status={item.status} compact />
              </motion.div>
            ))}
          </div>
          <Link href="/dashboard/stock/manage" className="primary-button mt-5 w-full">
            Manage Stock
            <ArrowRight size={16} />
          </Link>
        </DataPanel>
      </section>
    </motion.div>
  );
}
