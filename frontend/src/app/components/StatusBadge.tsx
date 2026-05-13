const statusClasses: Record<string, string> = {
  "In Stock": "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  "Low Stock": "border-orange-400/30 bg-orange-400/12 text-orange-300",
  Critical: "border-red-400/30 bg-red-400/12 text-red-300",
  Overstock: "border-violet-300/25 bg-violet-300/10 text-violet-200",
  "Order Only": "border-slate-400/20 bg-slate-400/8 text-slate-300",
  "Not Available": "border-slate-400/20 bg-slate-400/8 text-slate-300",
  Healthy: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  "Reorder Soon": "border-amber-300/25 bg-amber-300/10 text-amber-200",
  Pending: "border-orange-400/30 bg-orange-400/12 text-orange-300",
  Approved: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  Arrived: "border-sky-300/25 bg-sky-300/10 text-sky-200",
  Delivered: "border-sky-300/25 bg-sky-300/10 text-sky-200",
  Delayed: "border-red-400/30 bg-red-400/12 text-red-300",
  Refused: "border-red-400/30 bg-red-400/12 text-red-300",
  Received: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  Denied: "border-red-400/30 bg-red-400/12 text-red-300",
  Scheduled: "border-blue-300/25 bg-blue-300/10 text-blue-200",
};

const statusDescriptions: Record<string, string> = {
  Critical: "Current stock is below the minimum threshold.",
  "Low Stock": "Current stock is below recommended level but not critical.",
  Healthy: "Current stock is within the recommended operating range.",
  Overstock: "Current stock is significantly above recommended level.",
  "Reorder Soon": "Stock may fall below threshold soon based on demand.",
  "In Stock": "This part is available in the local store.",
  "Order Only": "This part is unavailable locally and should be added to a supplier order.",
  "Not Available": "This part is not currently available for local fulfillment.",
  Pending: "This order is waiting for manager review.",
  Scheduled: "This order has a planned handling time.",
  Approved: "This order has been accepted and is moving through fulfillment.",
  Delivered: "This order has arrived or has been handed over.",
  Received: "Supplier stock has been received into inventory.",
  Delayed: "This supplier order has been postponed.",
  Refused: "This supplier order was refused.",
  Denied: "This client order was denied.",
  Arrived: "Supplier delivery arrived and needs review.",
};

interface StatusBadgeProps {
  status: string;
  compact?: boolean;
  description?: string;
}

export function StatusBadge({ status, compact = false, description: customDescription }: StatusBadgeProps) {
  const description = customDescription || statusDescriptions[status];

  return (
    <span className="group/status relative z-10 inline-flex overflow-visible align-middle hover:z-[120] focus-within:z-[120]">
      <span
        tabIndex={description ? 0 : undefined}
        aria-label={description ? `${status}: ${description}` : status}
        className={`inline-flex items-center rounded-full border ${compact ? "px-2 py-0.5" : "px-2.5 py-1"} text-xs font-semibold ${
          statusClasses[status] ?? "border-white/10 bg-white/[0.04] text-slate-300"
        }`}
      >
        <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current shadow-[0_0_4px_currentColor]" />
        {status}
      </span>
      {description ? (
        <span className="pointer-events-none absolute left-1/2 top-[calc(100%+0.55rem)] z-[130] w-64 -translate-x-1/2 rounded-lg border border-white/[0.08] bg-[#080a10]/98 px-3 py-2 text-xs leading-5 text-slate-200 opacity-0 shadow-[0_18px_52px_rgba(0,0,0,0.55)] transition group-hover/status:opacity-100 group-focus-within/status:opacity-100">
          {description}
        </span>
      ) : null}
    </span>
  );
}
