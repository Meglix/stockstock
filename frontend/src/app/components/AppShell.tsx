"use client";

import { ReactNode, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { TopNav } from "./TopNav";
import { NotificationToasts } from "./NotificationCenter";
import { mergeStoredLocation } from "../utils/userLocation";

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  useEffect(() => {
    setSidebarCollapsed(localStorage.getItem("rrparts_sidebar_collapsed") === "true");
  }, []);

  const toggleSidebarCollapsed = () => {
    setSidebarCollapsed((current) => {
      const next = !current;
      localStorage.setItem("rrparts_sidebar_collapsed", String(next));
      return next;
    });
  };

  useEffect(() => {
    let isActive = true;

    async function verifySession() {
      const token = localStorage.getItem("auth_token");

      if (!token) {
        router.replace("/login");
        return;
      }

      try {
        const response = await fetch("/api/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!isActive) return;

        if (!response.ok) {
          localStorage.removeItem("auth_token");
          localStorage.removeItem("auth_user");
          router.replace("/login");
          return;
        }

        const user = mergeStoredLocation(await response.json());
        localStorage.setItem("auth_user", JSON.stringify(user));
        setAuthChecked(true);
      } catch {
        if (!isActive) return;
        localStorage.removeItem("auth_token");
        localStorage.removeItem("auth_user");
        router.replace("/login");
      }
    }

    verifySession();

    return () => {
      isActive = false;
    };
  }, [router]);

  if (!authChecked) {
    return (
      <div className="relative flex min-h-screen items-center justify-center bg-[#07090f] text-sm text-slate-400">
        Checking session...
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen bg-[#07090f] text-white">
      <div className="pointer-events-none absolute inset-0 app-ambient-bg" />
      <div className="noise-overlay" />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} collapsed={sidebarCollapsed} onToggleCollapsed={toggleSidebarCollapsed} />
      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <TopNav onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 px-4 py-5 scrollbar-thin sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
      <NotificationToasts />
    </div>
  );
}
