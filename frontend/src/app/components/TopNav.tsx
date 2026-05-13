"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { Bell, Menu, RefreshCw } from "lucide-react";
import { NotificationCenter } from "./NotificationCenter";
import { useDemoStore } from "../context/DemoStoreContext";

const pageTitles: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": { title: "Dashboard", subtitle: "Store operations, sales signals, and urgent stock pressure." },
  "/dashboard/parts": { title: "Parts", subtitle: "Full catalog with local stock and supplier-order options." },
  "/dashboard/stock": { title: "Stock", subtitle: "Current levels compared to recommended operating targets." },
  "/dashboard/stock/manage": { title: "Manage Stocks", subtitle: "Add, update, and clean up local inventory records." },
  "/dashboard/orders": { title: "Orders", subtitle: "Client demand and supplier purchasing workflows." },
  "/dashboard/forecasting": { title: "Forecasting", subtitle: "ML-style demand outlooks, horizon controls, and plain-language insights." },
};

interface TopNavProps {
  onMenuClick: () => void;
}

export function TopNav({ onMenuClick }: TopNavProps) {
  const pathname = usePathname();
  const [refreshing, setRefreshing] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const { unreadCount } = useDemoStore();
  const page = pageTitles[pathname] || pageTitles["/dashboard"];

  const handleRefresh = () => {
    setRefreshing(true);
    window.setTimeout(() => setRefreshing(false), 850);
  };

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.35 }}
      className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#07090f]/78 px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-8"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <button
            aria-label="Open navigation"
            onClick={onMenuClick}
            className="rounded-lg border border-white/10 p-2 text-slate-300 transition hover:border-orange-300/30 hover:text-orange-200 lg:hidden"
          >
            <Menu size={18} />
          </button>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-black tracking-normal text-white">{page.title}</h1>
            <p className="mt-1 hidden text-sm text-slate-500 sm:block">{page.subtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <button
            aria-label="Refresh dashboard"
            onClick={handleRefresh}
            className="rounded-xl border border-white/[0.08] bg-white/[0.04] p-2.5 text-slate-400 transition hover:border-orange-300/25 hover:text-orange-200"
          >
            <motion.span animate={{ rotate: refreshing ? 360 : 0 }} transition={{ duration: 0.75 }} className="block">
              <RefreshCw size={16} />
            </motion.span>
          </button>
          <button
            aria-label="Notifications"
            onClick={() => setNotificationsOpen((current) => !current)}
            className="relative rounded-xl border border-white/[0.08] bg-white/[0.04] p-2.5 text-slate-400 transition hover:border-orange-300/25 hover:text-orange-200"
          >
            <Bell size={16} />
            {unreadCount ? (
              <span className="absolute -right-1.5 -top-1.5 grid h-5 min-w-5 place-items-center rounded-full border border-[#07090f] bg-orange-400 px-1 text-[0.65rem] font-black text-black shadow-[0_0_16px_rgba(253,186,116,0.75)]">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            ) : null}
          </button>
        </div>
      </div>
      <NotificationCenter open={notificationsOpen} onClose={() => setNotificationsOpen(false)} />
    </motion.header>
  );
}
