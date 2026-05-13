"use client";

import { ReactNode } from "react";
import { motion } from "motion/react";

interface AuthLayoutProps {
  eyebrow: string;
  title: string;
  subtitle: string;
  children: ReactNode;
}

export function AuthLayout({ eyebrow, title, subtitle, children }: AuthLayoutProps) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[#050608] text-white">
      <img src="/automotive-interface.jpg" alt="" className="absolute inset-0 h-full w-full object-cover opacity-[0.24]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_28%,rgba(249,115,22,0.28),transparent_28%),linear-gradient(110deg,#050608_0%,rgba(5,6,8,0.9)_44%,rgba(5,6,8,0.62)_100%)]" />
      <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-[#050608] to-transparent" />
      <div className="noise-overlay" />

      <section className="relative z-10 grid min-h-screen grid-cols-1 lg:grid-cols-[1fr_520px]">
        <motion.div
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
          className="hidden flex-col justify-between px-10 py-10 lg:flex"
        >
          <div>
            <img className="auth-brand-logo auth-brand-logo--hero" src="/autoparts-stock-optimizer-logo-transparent.png" alt="AutoParts Stock Optimizer by RRParts" />
          </div>
          <div className="max-w-xl">
            <p className="mb-4 text-xs font-semibold uppercase text-orange-300/80">{eyebrow}</p>
            <h1 className="max-w-2xl text-5xl font-black leading-[0.96] tracking-normal text-white">
              Inventory intelligence for high-velocity parts.
            </h1>
            <p className="mt-5 max-w-lg text-base text-slate-300">
              Monitor parts, suppliers, stock health, and order signals through one cinematic command surface.
            </p>
          </div>
        </motion.div>

        <div className="flex items-center justify-center px-5 py-8">
          <motion.div
            initial={{ opacity: 0, y: 18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.45, ease: "easeOut" }}
            className="w-full max-w-[440px] rounded-2xl border border-white/10 bg-black/45 p-6 shadow-[0_24px_80px_rgba(0,0,0,0.55)] backdrop-blur-2xl"
          >
            <div className="mb-7">
              <img className="auth-brand-logo auth-brand-logo--card lg:hidden" src="/autoparts-stock-optimizer-logo-transparent.png" alt="AutoParts Stock Optimizer by RRParts" />
              <p className="text-xs font-semibold uppercase text-orange-300/80">{eyebrow}</p>
              <h1 className="mt-3 text-3xl font-black tracking-normal text-white">{title}</h1>
              <p className="mt-2 text-sm text-slate-400">{subtitle}</p>
            </div>
            {children}
          </motion.div>
        </div>
      </section>
    </main>
  );
}
