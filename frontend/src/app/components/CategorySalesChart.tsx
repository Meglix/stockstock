"use client";

import { useMemo, useState } from "react";
import { motion } from "motion/react";
import { SalesSeries, categorySalesSeries, months as defaultMonths } from "../data/inventory";

type HoverPoint = {
  category: string;
  month: string;
  value: number;
  color: string;
  x: number;
  y: number;
};

const chart = {
  width: 760,
  height: 310,
  left: 48,
  right: 18,
  top: 22,
  bottom: 42,
};

export function CategorySalesChart({ months = defaultMonths, series = categorySalesSeries }: { months?: string[]; series?: SalesSeries[] }) {
  const [hover, setHover] = useState<HoverPoint | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const activeMonths = months.length ? months : defaultMonths;
  const activeSeries = series.length ? series : categorySalesSeries;
  const allValues = activeSeries.flatMap((item) => item.values);
  const valueDomain = allValues.length ? allValues : [0, 1];
  const min = 0;
  const maxValue = Math.max(...valueDomain, 1);
  const max = Math.ceil((maxValue * 1.12) / 10) * 10;
  const innerWidth = chart.width - chart.left - chart.right;
  const innerHeight = chart.height - chart.top - chart.bottom;

  const seriesPaths = useMemo(() => {
    const xStep = innerWidth / Math.max(activeMonths.length - 1, 1);
    return activeSeries.map((series) => {
      const points = series.values.map((value, index) => {
        const x = chart.left + index * xStep;
        const y = chart.top + innerHeight - ((value - min) / (max - min)) * innerHeight;
        return { x, y, value, month: activeMonths[index] ?? "" };
      });
      return {
        ...series,
        points,
        path: points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" "),
      };
    });
  }, [activeMonths, activeSeries, innerHeight, innerWidth, max, min]);

  const yTicks = [0.25, 0.5, 0.75, 1].map((ratio) => Math.round(max * ratio));

  return (
    <div className="relative">
      <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-black/20">
        <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="h-[330px] w-full" role="img" aria-label="Monthly sales trends by category">
          <defs>
            <linearGradient id="salesFade" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="rgba(249,115,22,0.18)" />
              <stop offset="100%" stopColor="rgba(249,115,22,0)" />
            </linearGradient>
          </defs>
          <rect width={chart.width} height={chart.height} fill="rgba(255,255,255,0.015)" />
          {yTicks.map((tick) => {
            const y = chart.top + innerHeight - ((tick - min) / (max - min)) * innerHeight;
            return (
              <g key={tick}>
                <line x1={chart.left} x2={chart.width - chart.right} y1={y} y2={y} stroke="rgba(255,255,255,0.07)" />
                <text x={chart.left - 14} y={y + 4} textAnchor="end" fill="#64748b" fontSize="11">
                  {tick}
                </text>
              </g>
            );
          })}
          {activeMonths.map((month, index) => {
            const x = chart.left + index * (innerWidth / Math.max(activeMonths.length - 1, 1));
            return (
              <g key={month}>
                <line x1={x} x2={x} y1={chart.top} y2={chart.height - chart.bottom} stroke="rgba(255,255,255,0.04)" />
                <text x={x} y={chart.height - 16} textAnchor="middle" fill="#64748b" fontSize="11">
                  {month}
                </text>
              </g>
            );
          })}

          {seriesPaths.map((series, index) => (
            <g key={series.category} opacity={selectedCategory && selectedCategory !== series.category ? 0.32 : 1}>
              <motion.path
                d={series.path}
                fill="none"
                stroke={series.color}
                strokeWidth={selectedCategory === series.category ? 3.6 : 2.2}
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: selectedCategory && selectedCategory !== series.category ? 0.36 : 0.9 }}
                transition={{ duration: 0.8, delay: index * 0.08 }}
              />
              {series.points.map((point) => (
                <circle
                  key={`${series.category}-${point.month}`}
                  cx={point.x}
                  cy={point.y}
                  r={hover?.category === series.category && hover.month === point.month ? 5.5 : selectedCategory === series.category ? 4.3 : 3.4}
                  fill={series.color}
                  opacity={(hover && hover.category !== series.category) || (selectedCategory && selectedCategory !== series.category) ? 0.38 : 0.92}
                  className="cursor-pointer transition"
                  onClick={() => setSelectedCategory((current) => (current === series.category ? null : series.category))}
                  onMouseEnter={() => setHover({ category: series.category, month: point.month, value: point.value, color: series.color, x: point.x, y: point.y })}
                  onMouseLeave={() => setHover(null)}
                />
              ))}
            </g>
          ))}
        </svg>
      </div>

      {hover ? (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="pointer-events-none absolute rounded-xl border border-white/10 bg-[#080a10]/95 px-3 py-2 text-sm shadow-[0_16px_46px_rgba(0,0,0,0.45)]"
          style={{ left: `${(hover.x / chart.width) * 100}%`, top: `${(hover.y / chart.height) * 100}%`, transform: "translate(-50%, -110%)" }}
        >
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: hover.color }} />
            <span className="font-bold text-white">{hover.category}</span>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            {hover.month}: <span className="font-black text-orange-200">{hover.value}</span> sales units
          </p>
        </motion.div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {activeSeries.map((series) => (
          <button
            key={series.category}
            type="button"
            onClick={() => setSelectedCategory((current) => (current === series.category ? null : series.category))}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
              selectedCategory === series.category
                ? "border-orange-300/35 bg-orange-400/12 text-orange-100"
                : "border-white/[0.08] bg-white/[0.035] text-slate-300 hover:border-orange-300/25 hover:text-orange-100"
            }`}
          >
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: series.color }} />
            {series.category}
            {typeof series.total_sold === "number" ? <span className="text-slate-500">{series.total_sold.toLocaleString()}</span> : null}
          </button>
        ))}
      </div>
    </div>
  );
}
