"use client";

import { LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";

type Tone = "orange" | "steel" | "green" | "purple" | "red";

const toneClasses: Record<Tone, string> = {
  orange: "from-orange-500/20 to-orange-500/5 text-orange-300 border-orange-400/25",
  steel: "from-slate-300/14 to-slate-400/5 text-slate-200 border-white/12",
  green: "from-emerald-400/18 to-emerald-400/5 text-emerald-300 border-emerald-300/20",
  purple: "from-violet-400/18 to-violet-400/5 text-violet-300 border-violet-300/20",
  red: "from-red-400/18 to-red-400/5 text-red-300 border-red-300/20",
};

interface KpiCardProps {
  label: string;
  value: string | number;
  detail: string;
  icon: LucideIcon;
  tone?: Tone;
  index?: number;
  href?: string;
}

export function KpiCard({ label, value, detail, icon: Icon, tone = "orange", index = 0, href }: KpiCardProps) {
  const router = useRouter();
  const content = (
    <>
      <div className="flex items-start justify-between gap-4">
        <div className={`rounded-lg border bg-gradient-to-br p-2.5 ${toneClasses[tone]}`}>
          <Icon size={20} />
        </div>
        <div className="h-1.5 w-1.5 rounded-full bg-orange-400 shadow-[0_0_12px_rgba(249,115,22,0.72)]" />
      </div>
      <div className="mt-5">
        <p className="text-sm text-slate-400">{label}</p>
        <p className="mt-1 text-3xl font-black tracking-normal text-white">{value}</p>
        <p className="mt-2 text-xs text-slate-500">{detail}</p>
      </div>
    </>
  );

  if (href) {
    return (
      <motion.button
        type="button"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.055, duration: 0.38, ease: "easeOut" }}
        whileHover={{ y: -3 }}
        onClick={() => router.push(href)}
        className="premium-card premium-card--clickable group w-full text-left"
      >
        {content}
      </motion.button>
    );
  }

  return (
    <motion.article
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.055, duration: 0.38, ease: "easeOut" }}
      whileHover={{ y: -2 }}
      className="premium-card group"
    >
      {content}
    </motion.article>
  );
}
