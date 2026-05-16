"use client";

import { useMemo, useState } from "react";
import { motion } from "motion/react";
import { ForecastHorizon, ForecastPoint, displayPointDate, forecastHorizons } from "../data/forecasting";

type HoverPoint = ForecastPoint & {
  x: number;
  y: number;
};

const chart = {
  width: 860,
  height: 360,
  left: 52,
  right: 24,
  top: 28,
  bottom: 46,
};

function makePath(points: Array<{ x: number; y: number }>) {
  if (points.length < 2) return "";
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
}

function makeBandPath(top: Array<{ x: number; y: number }>, bottom: Array<{ x: number; y: number }>) {
  if (!top.length || !bottom.length) return "";
  return `${makePath(top)} L ${bottom
    .slice()
    .reverse()
    .map((point) => `${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" L ")} Z`;
}

export function DemandForecastChart({
  points,
  horizon,
  onHorizonChange,
  compact = false,
  emptyMessage = "Not enough normalized forecast data for this selection.",
}: {
  points: ForecastPoint[];
  horizon: ForecastHorizon;
  onHorizonChange?: (horizon: ForecastHorizon) => void;
  compact?: boolean;
  emptyMessage?: string;
}) {
  const [hover, setHover] = useState<HoverPoint | null>(null);
  const innerWidth = chart.width - chart.left - chart.right;
  const innerHeight = chart.height - chart.top - chart.bottom;
  const domainValues = points.flatMap((point) => [point.actual, point.forecast, point.confidenceHigh]).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const maxValue = Math.max(...domainValues, 1);
  const max = Math.ceil((maxValue * 1.12) / 10) * 10;

  const mapped = useMemo(() => {
    const xStep = innerWidth / Math.max(points.length - 1, 1);
    const mapY = (value: number) => chart.top + innerHeight - (value / max) * innerHeight;

    return points.map((point, index) => {
      const x = chart.left + index * xStep;
      return {
        ...point,
        x,
        actualY: typeof point.actual === "number" ? mapY(point.actual) : undefined,
        forecastY: typeof point.forecast === "number" ? mapY(point.forecast) : undefined,
        lowY: typeof point.confidenceLow === "number" ? mapY(point.confidenceLow) : undefined,
        highY: typeof point.confidenceHigh === "number" ? mapY(point.confidenceHigh) : undefined,
      };
    });
  }, [innerHeight, innerWidth, max, points]);

  const actualPath = makePath(mapped.filter((point) => typeof point.actualY === "number").map((point) => ({ x: point.x, y: point.actualY ?? 0 })));
  const forecastPoints = mapped.filter((point) => typeof point.forecastY === "number");
  const forecastPath = makePath(forecastPoints.map((point) => ({ x: point.x, y: point.forecastY ?? 0 })));
  const confidencePoints = mapped.filter((point) => typeof point.highY === "number" && typeof point.lowY === "number");
  const confidencePath = makeBandPath(
    confidencePoints.map((point) => ({ x: point.x, y: point.highY ?? 0 })),
    confidencePoints.map((point) => ({ x: point.x, y: point.lowY ?? 0 })),
  );
  const yTicks = [0.25, 0.5, 0.75, 1].map((ratio) => Math.round(max * ratio));
  const hasForecastLine = forecastPoints.length >= 2;

  return (
    <div className="relative">
      {onHorizonChange ? (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 text-xs font-semibold uppercase text-slate-500">
            <span className="h-2 w-2 rounded-full bg-orange-300" />
            Forecast horizon
          </div>
          <div className="segmented-tabs forecast-horizon-tabs">
            {forecastHorizons.map((item) => (
              <button key={item} type="button" className={horizon === item ? "is-active" : ""} onClick={() => onHorizonChange(item)}>
                {item} days
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-black/20">
        <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className={compact ? "h-[320px] w-full" : "h-[390px] w-full"} role="img" aria-label="Demand forecast chart">
          <defs>
            <linearGradient id="forecastBand" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="rgba(251,146,60,0.24)" />
              <stop offset="100%" stopColor="rgba(251,146,60,0.02)" />
            </linearGradient>
            <linearGradient id="forecastStroke" x1="0" x2="1" y1="0" y2="0">
              <stop offset="0%" stopColor="#fb923c" />
              <stop offset="100%" stopColor="#fed7aa" />
            </linearGradient>
          </defs>
          <rect width={chart.width} height={chart.height} fill="rgba(255,255,255,0.014)" />

          {yTicks.map((tick) => {
            const y = chart.top + innerHeight - (tick / max) * innerHeight;
            return (
              <g key={tick}>
                <line x1={chart.left} x2={chart.width - chart.right} y1={y} y2={y} stroke="rgba(255,255,255,0.07)" />
                <text x={chart.left - 14} y={y + 4} textAnchor="end" fill="#64748b" fontSize="11">
                  {tick}
                </text>
              </g>
            );
          })}

          {mapped.map((point, index) => {
            const shouldLabel = compact ? index % 4 === 0 || index === mapped.length - 1 : index % 3 === 0 || index === mapped.length - 1;
            return (
              <g key={`${point.label}-${index}`}>
                <line x1={point.x} x2={point.x} y1={chart.top} y2={chart.height - chart.bottom} stroke="rgba(255,255,255,0.038)" />
                {shouldLabel ? (
                  <text x={point.x} y={chart.height - 18} textAnchor="middle" fill="#64748b" fontSize="11">
                    {point.label}
                  </text>
                ) : null}
              </g>
            );
          })}

          <motion.path
            d={confidencePath}
            fill="url(#forecastBand)"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.55 }}
          />
          <motion.path
            d={forecastPath}
            fill="none"
            stroke="url(#forecastStroke)"
            strokeWidth="2.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 0.95 }}
            transition={{ duration: 0.85 }}
          />
          <motion.path
            d={actualPath}
            fill="none"
            stroke="#7dd3fc"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 0.9 }}
            transition={{ duration: 0.75, delay: 0.08 }}
          />

          {mapped.map((point, index) => (
            <g key={`hit-${point.date ?? point.label}-${index}`}>
              <rect
                x={point.x - 12}
                y={chart.top}
                width={24}
                height={innerHeight}
                fill="transparent"
                className="cursor-crosshair"
                onMouseEnter={() => setHover({ ...point, y: point.forecastY ?? point.actualY ?? chart.top })}
                onMouseMove={() => setHover({ ...point, y: point.forecastY ?? point.actualY ?? chart.top })}
                onMouseLeave={() => setHover(null)}
              />
              {typeof point.forecastY === "number" ? <circle cx={point.x} cy={point.forecastY} r={hover?.label === point.label ? 4.8 : 3.2} fill="#fb923c" opacity="0.95" /> : null}
              {typeof point.actualY === "number" ? <circle cx={point.x} cy={point.actualY} r={hover?.label === point.label ? 4.4 : 3} fill="#7dd3fc" opacity="0.9" /> : null}
            </g>
          ))}
        </svg>
        {!hasForecastLine ? (
          <div className="absolute inset-x-4 top-1/2 -translate-y-1/2 rounded-xl border border-orange-300/18 bg-[#090b11]/92 px-4 py-3 text-center text-sm font-semibold text-slate-300 shadow-[0_16px_46px_rgba(0,0,0,0.35)]">
            {emptyMessage}
          </div>
        ) : null}
      </div>

      {hover ? (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="pointer-events-none absolute rounded-xl border border-white/10 bg-[#080a10]/95 px-3 py-2 text-sm shadow-[0_16px_46px_rgba(0,0,0,0.45)]"
          style={{ left: `${(hover.x / chart.width) * 100}%`, top: `${(hover.y / chart.height) * 100}%`, transform: "translate(-50%, -112%)" }}
        >
          <p className="text-xs font-bold uppercase text-slate-500">{displayPointDate(hover)}</p>
          <div className="mt-2 space-y-1">
            {typeof hover.actual === "number" ? (
              <p className="flex items-center gap-2 text-xs text-slate-300">
                <span className="h-2 w-2 rounded-full bg-sky-300" />
                Actual <strong className="text-white">{hover.actual}</strong>
              </p>
            ) : null}
            {typeof hover.forecast === "number" ? <p className="flex items-center gap-2 text-xs text-slate-300">
              <span className="h-2 w-2 rounded-full bg-orange-300" />
              Forecast <strong className="text-orange-100">{hover.forecast}</strong>
            </p> : null}
            {typeof hover.confidenceLow === "number" && typeof hover.confidenceHigh === "number" ? <p className="text-xs text-slate-500">
              Confidence {hover.confidenceLow}-{hover.confidenceHigh}
            </p> : null}
          </div>
        </motion.div>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs font-semibold text-slate-400">
        <span className="inline-flex items-center gap-2">
          <span className="h-2 w-5 rounded-full bg-sky-300" />
          Actual demand
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-2 w-5 rounded-full bg-orange-300" />
          Forecast demand
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-2 w-5 rounded-full bg-orange-300/25" />
          Confidence band
        </span>
      </div>
    </div>
  );
}
