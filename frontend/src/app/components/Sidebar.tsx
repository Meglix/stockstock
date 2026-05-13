"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { BarChart3, BrainCircuit, LayoutDashboard, LogOut, Package, PanelLeftClose, PanelLeftOpen, ShoppingCart, X } from "lucide-react";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, path: "/dashboard" },
  { label: "Parts", icon: Package, path: "/dashboard/parts" },
  { label: "Stock", icon: BarChart3, path: "/dashboard/stock" },
  { label: "Orders", icon: ShoppingCart, path: "/dashboard/orders" },
  { label: "Forecasting", icon: BrainCircuit, path: "/dashboard/forecasting" },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

type StoredUser = {
  username?: string;
  email?: string;
  full_name?: string | null;
  company?: string | null;
  location?: string | null;
  role?: string;
};

function readStoredUser(): StoredUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem("auth_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

export function Sidebar({ isOpen, onClose, collapsed, onToggleCollapsed }: SidebarProps) {
  const pathname = usePathname();
  const [user, setUser] = useState<StoredUser | null>(null);

  useEffect(() => {
    setUser(readStoredUser());
  }, [pathname]);

  const handleSignOut = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_user");
    onClose();
  };
  const displayName = user?.full_name || user?.username || "Signed in";
  const displayDetail = [user?.location, user?.company, user?.email].filter(Boolean).join(" / ") || user?.role || "";
  const initial = displayName.trim().charAt(0).toUpperCase() || "U";

  return (
    <>
      <button
        aria-label="Close navigation"
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity lg:hidden ${isOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}
      />
      <motion.aside
        initial={{ x: -24, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.38, ease: "easeOut" }}
        className={`fixed inset-y-0 left-0 z-50 flex w-[268px] shrink-0 flex-col border-r border-white/[0.08] bg-[#090b11]/95 shadow-[20px_0_70px_rgba(0,0,0,0.4)] backdrop-blur-xl transition-[width,transform] duration-300 ease-out lg:static lg:inset-auto lg:z-10 lg:min-h-screen lg:self-stretch lg:translate-x-0 ${
          collapsed ? "lg:w-[86px]" : "lg:w-[268px]"
        } ${isOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className={`flex items-center border-b border-white/[0.08] px-4 py-5 transition-all duration-300 ${collapsed ? "lg:justify-center" : "justify-between"}`}>
          <Link href="/dashboard" onClick={onClose} aria-label="Go to dashboard" className={`brand-logo brand-logo--sidebar ${collapsed ? "brand-logo--sidebar-collapsed" : ""}`}>
            <img src="/autoparts-stock-optimizer-logo-sidebar-transparent.png" alt="AutoParts Stock Optimizer by RRParts" />
          </Link>
          <div className={`flex items-center gap-2 ${collapsed ? "lg:hidden" : ""}`}>
            <button
              type="button"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              onClick={onToggleCollapsed}
              className="hidden rounded-lg border border-white/10 p-2 text-slate-400 transition hover:border-orange-300/30 hover:text-orange-200 lg:inline-flex"
            >
              {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
            </button>
            <button
              aria-label="Close sidebar"
              onClick={onClose}
              className="rounded-lg border border-white/10 p-2 text-slate-400 transition hover:border-orange-300/30 hover:text-orange-200 lg:hidden"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {collapsed ? (
          <button
            type="button"
            aria-label="Expand sidebar"
            onClick={onToggleCollapsed}
            className="mx-auto mt-3 hidden rounded-lg border border-white/10 p-2 text-slate-400 transition hover:border-orange-300/30 hover:text-orange-200 lg:inline-flex"
          >
            <PanelLeftOpen size={16} />
          </button>
        ) : null}

        <nav className="flex-1 px-3 py-4">
          <div className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = item.path === "/dashboard" ? pathname === item.path : pathname.startsWith(item.path);

              return (
                <Link
                  key={item.path}
                  href={item.path}
                  onClick={onClose}
                  className={`group/sidebar relative flex items-center rounded-xl py-3 text-sm transition ${collapsed ? "lg:justify-center lg:px-0" : "gap-3 px-3"} ${
                    active ? "text-orange-200" : "text-slate-400 hover:bg-white/[0.04] hover:text-white"
                  }`}
                >
                  {active ? (
                    <motion.span
                      layoutId="sidebar-active"
                      className="absolute inset-0 rounded-xl border border-orange-300/20 bg-orange-400/10 shadow-[inset_0_0_18px_rgba(249,115,22,0.07)]"
                    />
                  ) : null}
                  <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.035]">
                    <Icon size={17} />
                  </span>
                  <span className={`relative z-10 overflow-hidden whitespace-nowrap font-semibold transition-all duration-300 ${collapsed ? "lg:w-0 lg:opacity-0" : "w-auto opacity-100"}`}>
                    {item.label}
                  </span>
                  {active ? (
                    <span className={`relative z-10 h-1.5 w-1.5 rounded-full bg-orange-300 shadow-[0_0_10px_rgba(253,186,116,0.72)] ${collapsed ? "lg:absolute lg:right-1.5 lg:top-1/2 lg:-translate-y-1/2" : "ml-auto"}`} />
                  ) : null}
                  {collapsed ? (
                    <span className="pointer-events-none absolute left-[calc(100%+0.65rem)] top-1/2 z-50 hidden -translate-y-1/2 whitespace-nowrap rounded-lg border border-white/[0.08] bg-[#0a0d13]/96 px-2.5 py-1.5 text-xs font-semibold text-slate-200 opacity-0 shadow-[0_12px_34px_rgba(0,0,0,0.35)] transition group-hover/sidebar:opacity-100 lg:block">
                      {item.label}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="p-4">
          <div className={`rounded-xl border border-white/[0.08] bg-white/[0.035] p-3 transition-all duration-300 ${collapsed ? "lg:p-2" : ""}`}>
            <div className={`mb-3 flex items-center gap-3 ${collapsed ? "lg:mb-2 lg:justify-center" : ""}`}>
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-orange-400 to-orange-700 text-sm font-black text-white">
                {initial}
              </div>
              <div className={`min-w-0 transition-all duration-300 ${collapsed ? "lg:hidden" : ""}`}>
                <p className="truncate text-sm font-bold text-white">{displayName}</p>
                <p className="truncate text-xs text-slate-500">{displayDetail}</p>
              </div>
            </div>
            <Link
              href="/login"
              onClick={handleSignOut}
              className={`group/sidebar relative flex items-center justify-center gap-2 rounded-lg border border-white/[0.08] px-3 py-2 text-xs font-semibold text-slate-400 transition hover:border-orange-300/25 hover:text-orange-200 ${
                collapsed ? "lg:px-2" : ""
              }`}
            >
              <LogOut size={14} />
              <span className={collapsed ? "lg:hidden" : ""}>Sign out</span>
              {collapsed ? (
                <span className="pointer-events-none absolute left-[calc(100%+0.65rem)] top-1/2 z-50 hidden -translate-y-1/2 whitespace-nowrap rounded-lg border border-white/[0.08] bg-[#0a0d13]/96 px-2.5 py-1.5 text-xs font-semibold text-slate-200 opacity-0 shadow-[0_12px_34px_rgba(0,0,0,0.35)] transition group-hover/sidebar:opacity-100 lg:block">
                  Sign out
                </span>
              ) : null}
            </Link>
          </div>
        </div>
      </motion.aside>
    </>
  );
}
