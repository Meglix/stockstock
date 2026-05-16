"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { Ban, BadgeCheck, Check, Clock3, PackageCheck, RotateCcw, ShieldCheck, ShoppingCart, Timer, Trash2, TriangleAlert, Truck, X } from "lucide-react";
import { DataPanel } from "../components/DataPanel";
import { KpiCard } from "../components/KpiCard";
import { StatusBadge } from "../components/StatusBadge";
import { ClientOrderAvailabilityShortage, useDemoStore } from "../context/DemoStoreContext";
import { CatalogProduct, ClientOrder, OrderLine, SupplierOrder } from "../data/inventory";

type OrdersTab = "clients" | "suppliers";
type ClientGroup = "needs-review" | "accepted" | "denied" | "backorders-waiting" | "complete" | "backorders-ready";
type SupplierGroup = "needs-review" | "in-progress" | "approved" | "complete" | "denied";

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function formatArrival(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return formatDateTime(value);
}

function defaultSoonTime() {
  const date = new Date(Date.now() + 60_000);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function lineTotal(line: OrderLine) {
  return line.quantity * line.unitPrice;
}

function orderTotal(lines: OrderLine[]) {
  return lines.reduce((sum, line) => sum + lineTotal(line), 0);
}

function orderShortage(order: ClientOrder) {
  return order.shortageQuantity ?? order.items.reduce((sum, line) => sum + (line.shortageQuantity ?? 0), 0);
}

function formatOrderLine(line: OrderLine) {
  const shortage = line.shortageQuantity ? ` (${line.shortageQuantity} short)` : "";
  return `${line.quantity}x ${line.name}${shortage}`;
}

function integerQuantity(value: string, fallback = 1) {
  const parsed = Number.parseInt(value.replace(/\D/g, ""), 10);
  return Number.isFinite(parsed) ? Math.max(1, parsed) : fallback;
}

function clientGroupFromParam(value: string | null): ClientGroup | null {
  if (value === "needs-review" || value === "accepted" || value === "denied" || value === "backorders-waiting" || value === "complete" || value === "backorders-ready") return value;
  return null;
}

function supplierGroupFromParam(value: string | null): SupplierGroup | null {
  if (value === "needs-review" || value === "in-progress" || value === "approved" || value === "complete" || value === "denied") return value;
  return null;
}

function GroupTabs<T extends string>({
  groups,
  active,
  onChange,
}: {
  groups: Array<{ id: T; label: string; count: number }>;
  active: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="order-group-tabs">
      {groups.map((group) => (
        <button key={group.id} type="button" className={active === group.id ? "is-active" : ""} onClick={() => onChange(group.id)}>
          {group.label}
          <span>{group.count}</span>
        </button>
      ))}
    </div>
  );
}

export function Orders() {
  const params = useSearchParams();
  const {
    products,
    clientOrders,
    supplierOrders,
    ordersLoading,
    ordersError,
    refreshOrderWorkflows,
    createSupplierOrder,
    receiveSupplierDelivery,
    postponeSupplierDelivery,
    refuseSupplierDelivery,
    approveClientOrder,
    completeClientOrder,
    previewClientOrderApproval,
    denyClientOrder,
    scheduleClientOrder,
  } = useDemoStore();
  const [activeTab, setActiveTab] = useState<OrdersTab>("clients");
  const [activeClientGroup, setActiveClientGroup] = useState<ClientGroup>("needs-review");
  const [activeSupplierGroup, setActiveSupplierGroup] = useState<SupplierGroup>("needs-review");
  const [selectedSupplier, setSelectedSupplier] = useState("Bosch");
  const [cart, setCart] = useState<OrderLine[]>([]);
  const [scheduleTimes, setScheduleTimes] = useState<Record<string, string>>({});
  const [postponeTimes, setPostponeTimes] = useState<Record<string, string>>({});
  const [queryApplied, setQueryApplied] = useState(false);
  const [submittingOrder, setSubmittingOrder] = useState(false);
  const [approvalWarning, setApprovalWarning] = useState<{ order: ClientOrder; shortages: ClientOrderAvailabilityShortage[] } | null>(null);
  const scrollRestoreTimer = useRef<number | null>(null);

  const suppliers = useMemo(() => Array.from(new Set(products.map((product) => product.supplier))).filter(Boolean), [products]);
  const supplierProducts = useMemo(() => products.filter((product) => product.supplier === selectedSupplier), [products, selectedSupplier]);

  const needsReviewClientOrders = clientOrders.filter((order) => order.status === "Pending" || order.status === "Scheduled");
  const backorderReadyOrders = clientOrders.filter((order) => order.status === "Approved" && order.fulfillmentStatus === "ready");
  const backorderWaitingOrders = clientOrders.filter((order) => order.status === "Approved" && (order.fulfillmentStatus === "backorder" || order.fulfillmentStatus === "partial"));
  const acceptedClientOrders = clientOrders.filter(
    (order) => order.status === "Approved" && order.fulfillmentStatus !== "ready" && order.fulfillmentStatus !== "backorder" && order.fulfillmentStatus !== "partial",
  );
  const deniedClientOrders = clientOrders.filter((order) => order.status === "Denied");
  const completeClientOrders = clientOrders.filter((order) => order.status === "Delivered");

  const supplierReviewOrders = supplierOrders.filter((order) => order.status === "Delivered" && !order.stockApplied);
  const supplierProgressOrders = supplierOrders.filter((order) => order.status === "Pending" || order.status === "Delayed");
  const supplierApprovedOrders = supplierOrders.filter((order) => order.status === "Approved");
  const supplierCompleteOrders = supplierOrders.filter((order) => order.status === "Received" || (order.status === "Delivered" && order.stockApplied));
  const supplierDeniedOrders = supplierOrders.filter((order) => order.status === "Refused");

  const clientGroups = [
    { id: "needs-review" as const, label: "Needs Review", count: needsReviewClientOrders.length, orders: needsReviewClientOrders, title: "Client Orders Needing Review", eyebrow: "Approve, deny, or schedule" },
    { id: "accepted" as const, label: "Accepted", count: acceptedClientOrders.length, orders: acceptedClientOrders, title: "Accepted Client Orders", eyebrow: "Approved client demand" },
    { id: "denied" as const, label: "Denied", count: deniedClientOrders.length, orders: deniedClientOrders, title: "Denied Client Orders", eyebrow: "Refused demand" },
    { id: "backorders-waiting" as const, label: "Backorders Waiting", count: backorderWaitingOrders.length, orders: backorderWaitingOrders, title: "Backorders Waiting", eyebrow: "Supplier replenishment in progress" },
    { id: "complete" as const, label: "Client Orders Complete", count: completeClientOrders.length, orders: completeClientOrders, title: "Client Orders Complete", eyebrow: "Fulfilled client orders" },
    { id: "backorders-ready" as const, label: "Backorders Ready", count: backorderReadyOrders.length, orders: backorderReadyOrders, title: "Backorders Ready", eyebrow: "Supplier stock received" },
  ];
  const supplierGroups = [
    { id: "needs-review" as const, label: "Needs Review", count: supplierReviewOrders.length, orders: supplierReviewOrders, title: "Supplier Deliveries to Review", eyebrow: "Receive, postpone, or refuse" },
    { id: "in-progress" as const, label: "In Progress", count: supplierProgressOrders.length, orders: supplierProgressOrders, title: "Supplier Orders in Progress", eyebrow: "Placed orders and postponements" },
    { id: "approved" as const, label: "Approved", count: supplierApprovedOrders.length, orders: supplierApprovedOrders, title: "Approved Supplier Orders", eyebrow: "Supplier-confirmed demand" },
    { id: "complete" as const, label: "Received / Complete", count: supplierCompleteOrders.length, orders: supplierCompleteOrders, title: "Received Supplier Orders", eyebrow: "Stock-updated history" },
    { id: "denied" as const, label: "Refused / Denied", count: supplierDeniedOrders.length, orders: supplierDeniedOrders, title: "Refused Supplier Orders", eyebrow: "Supplier orders not accepted" },
  ];
  const activeClientGroupData = clientGroups.find((group) => group.id === activeClientGroup) ?? clientGroups[0];
  const activeSupplierGroupData = supplierGroups.find((group) => group.id === activeSupplierGroup) ?? supplierGroups[0];

  const approvedClientCount = clientOrders.filter((order) => order.status === "Approved").length;
  const approvedSupplierCount = supplierOrders.filter((order) => order.status === "Approved").length;
  const deniedOrders = deniedClientOrders.length + supplierDeniedOrders.length;
  const pendingOrders = needsReviewClientOrders.length + supplierReviewOrders.length;
  const supplierDemandQuantity = supplierOrders.reduce((sum, order) => sum + order.items.reduce((lineSum, line) => lineSum + line.quantity, 0), 0);

  const addToCart = (product: CatalogProduct, quantity = 1) => {
    setCart((current) => {
      const existing = current.find((line) => line.productId === product.id);
      if (existing) return current.map((line) => (line.productId === product.id ? { ...line, quantity: line.quantity + quantity } : line));
      return [...current, { productId: product.id, name: product.name, sku: product.sku, quantity, unitPrice: product.unitPrice, location: product.location }];
    });
  };

  const preserveScrollAfter = async (action: () => Promise<void>) => {
    const scrollX = window.scrollX;
    const scrollY = window.scrollY;
    if (scrollRestoreTimer.current) window.clearTimeout(scrollRestoreTimer.current);
    await action();
    window.requestAnimationFrame(() => window.scrollTo(scrollX, scrollY));
    scrollRestoreTimer.current = window.setTimeout(() => window.scrollTo(scrollX, scrollY), 120);
  };

  useEffect(() => {
    const tab = params.get("tab");
    if (tab === "suppliers" || tab === "clients") setActiveTab(tab);
    const group = params.get("group");
    const clientGroup = clientGroupFromParam(group);
    const supplierGroup = supplierGroupFromParam(group);
    if (clientGroup) setActiveClientGroup(clientGroup);
    if (supplierGroup) setActiveSupplierGroup(supplierGroup);
  }, [params]);

  useEffect(() => {
    if (!suppliers.length || suppliers.includes(selectedSupplier)) return;
    setSelectedSupplier(suppliers[0]);
  }, [selectedSupplier, suppliers]);

  useEffect(() => {
    if (queryApplied || products.length === 0) return;
    const supplier = params.get("supplier");
    const productId = params.get("product");
    if (supplier) setSelectedSupplier(supplier);
    if (productId) {
      const product = products.find((item) => item.id === productId);
      if (product) {
        setSelectedSupplier(product.supplier);
        setActiveTab("suppliers");
        addToCart(product);
      }
    }
    setQueryApplied(true);
  }, [params, products, queryApplied]);

  const confirmSupplierOrder = async () => {
    if (!cart.length || submittingOrder) return;
    setSubmittingOrder(true);
    try {
      const created = await createSupplierOrder(selectedSupplier, cart);
      if (created) setCart([]);
    } finally {
      setSubmittingOrder(false);
    }
  };

  const requestClientApproval = async (order: ClientOrder) => {
    try {
      const preview = await previewClientOrderApproval(order.id);
      if (!preview.can_fulfill && preview.shortages.length > 0) {
        setApprovalWarning({ order, shortages: preview.shortages });
        return;
      }
      await preserveScrollAfter(() => approveClientOrder(order.id));
    } catch (error) {
      console.warn("Could not preview client order stock availability", error);
    }
  };

  const confirmBackorderApproval = async () => {
    if (!approvalWarning) return;
    const orderId = approvalWarning.order.id;
    setApprovalWarning(null);
    await preserveScrollAfter(() => approveClientOrder(orderId));
  };

  const renderClientOrder = (order: ClientOrder) => (
    <motion.div layout="position" key={order.id} className="client-order-card">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="sku-chip">{order.id}</span>
          <StatusBadge status={order.status} compact />
          {order.fulfillmentStatus && order.fulfillmentStatus !== "unreviewed" ? <span className="rounded-full border border-white/[0.08] bg-white/[0.035] px-2 py-1 text-xs font-semibold text-slate-300">{order.fulfillmentStatus}</span> : null}
          {orderShortage(order) ? <span className="rounded-full border border-orange-300/25 bg-orange-400/10 px-2 py-1 text-xs font-semibold text-orange-200">{orderShortage(order)} short</span> : null}
          {order.scheduledFor ? <span className="rounded-full border border-blue-300/20 bg-blue-400/10 px-2 py-1 text-xs font-semibold text-blue-200">Delivery {formatDateTime(order.scheduledFor)}</span> : null}
        </div>
        <h3 className="mt-3 text-lg font-black text-white">{order.client}</h3>
        <p className="mt-1 text-sm text-slate-500">{order.items.map(formatOrderLine).join(", ")}</p>
        <p className="mt-2 text-xs text-slate-600">Requested delivery time: {order.requestedTime || "Flexible"}</p>
        {order.location ? <p className="mt-1 text-xs text-slate-600">Location: {order.location}</p> : null}
      </div>
      <div className="flex flex-col gap-2 sm:min-w-[280px]">
        {order.status === "Pending" || order.status === "Scheduled" ? (
          <>
            <div className="grid grid-cols-2 gap-2">
              <button className="primary-button min-h-10 px-3 py-2 text-sm" onClick={() => requestClientApproval(order)}><Check size={15} /> Approve</button>
              <button className="danger-action" onClick={() => void preserveScrollAfter(() => denyClientOrder(order.id))}><X size={15} /> Deny</button>
            </div>
            <div className="grid grid-cols-[1fr_auto] gap-2">
              <input className="time-input" type="time" value={scheduleTimes[order.id] ?? defaultSoonTime()} onChange={(event) => setScheduleTimes((current) => ({ ...current, [order.id]: event.target.value }))} />
              <button className="secondary-action" onClick={() => void preserveScrollAfter(() => scheduleClientOrder(order.id, scheduleTimes[order.id] ?? defaultSoonTime()))}><Clock3 size={15} /> Schedule</button>
            </div>
          </>
        ) : null}
        {order.status === "Approved" && order.fulfillmentStatus === "ready" ? (
          <button className="primary-button min-h-10 px-3 py-2 text-sm" onClick={() => void preserveScrollAfter(() => completeClientOrder(order.id))}>
            <PackageCheck size={15} />
            Complete order
          </button>
        ) : null}
      </div>
    </motion.div>
  );

  const renderSupplierOrder = (order: SupplierOrder) => (
    <motion.div layout="position" key={order.id} className="order-history-row">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="sku-chip">{order.id}</span>
          <StatusBadge status={order.stockApplied ? "Received" : order.status === "Delivered" && !order.stockApplied ? "Arrived" : order.status} compact />
          {order.stockApplied ? <span className="rounded-full border border-emerald-300/20 bg-emerald-400/10 px-2 py-1 text-xs font-semibold text-emerald-200">Stock updated</span> : null}
        </div>
        <p className="mt-3 font-bold text-white">{order.supplier}</p>
        <p className="mt-1 text-sm text-slate-500">{order.items.map(formatOrderLine).join(", ")}</p>
        <p className="mt-1 text-xs text-slate-600">
          {order.receivedAt
            ? `Received: ${formatDateTime(order.receivedAt)}`
            : order.postponedUntil
              ? `Postponed until: ${formatDateTime(order.postponedUntil)}`
              : `Estimated arrival: ${formatArrival(order.estimatedArrival)}`}
        </p>
        {order.location ? <p className="mt-1 text-xs text-slate-600">Location: {order.location}</p> : null}
      </div>
      {order.status === "Delivered" && !order.stockApplied ? (
        <div className="flex flex-col gap-2 sm:min-w-[240px]">
          <button className="primary-button min-h-10 px-3 py-2 text-sm" onClick={() => void preserveScrollAfter(() => receiveSupplierDelivery(order.id))}><PackageCheck size={15} /> Receive delivery</button>
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <input className="time-input" type="time" value={postponeTimes[order.id] ?? defaultSoonTime()} onChange={(event) => setPostponeTimes((current) => ({ ...current, [order.id]: event.target.value }))} />
            <button className="secondary-action" onClick={() => void preserveScrollAfter(() => postponeSupplierDelivery(order.id, postponeTimes[order.id] ?? defaultSoonTime()))}><Clock3 size={15} /></button>
          </div>
          <button className="danger-action" onClick={() => void preserveScrollAfter(() => refuseSupplierDelivery(order.id))}><X size={15} /> Refuse</button>
        </div>
      ) : null}
    </motion.div>
  );

  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="space-y-5">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Pending Orders" value={pendingOrders} detail="Needs manager action" icon={Timer} tone="orange" index={0} />
        <KpiCard label="Approved Client Orders" value={approvedClientCount} detail="Accepted client demand" icon={BadgeCheck} tone="green" index={1} />
        <KpiCard label="Approved Supplier Orders" value={approvedSupplierCount} detail="Confirmed supplier flow" icon={Truck} tone="steel" index={2} />
        <KpiCard label="Orders Denied" value={deniedOrders} detail="Client denied or supplier refused" icon={Ban} tone="red" index={3} />
      </section>

      {ordersError ? <div className="rounded-xl border border-red-300/20 bg-red-400/10 px-4 py-3 text-sm text-red-100">{ordersError}</div> : null}
      {ordersLoading ? <div className="rounded-xl border border-white/[0.08] bg-white/[0.035] px-4 py-3 text-sm text-slate-400">Loading backend orders...</div> : null}

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="segmented-tabs flex-1">
          <button className={activeTab === "clients" ? "is-active" : ""} onClick={() => setActiveTab("clients")}>
            Orders from Clients
            <span>{clientOrders.length}</span>
          </button>
          <button className={activeTab === "suppliers" ? "is-active" : ""} onClick={() => setActiveTab("suppliers")}>
            Orders to Suppliers
            <span>{supplierOrders.length}</span>
          </button>
        </div>
        <button className="secondary-action min-h-10" onClick={() => void refreshOrderWorkflows()} disabled={ordersLoading}>
          <RotateCcw size={15} />
          Refresh
        </button>
      </div>

      {activeTab === "clients" ? (
        <div className="space-y-5">
          <GroupTabs groups={clientGroups.map(({ id, label, count }) => ({ id, label, count }))} active={activeClientGroup} onChange={setActiveClientGroup} />
          <DataPanel title={activeClientGroupData.title} eyebrow={activeClientGroupData.eyebrow} action={<span className="panel-pill"><ShoppingCart size={13} /> {activeClientGroupData.count} orders</span>}>
            {activeClientGroupData.orders.length ? (
              <div className="grid grid-cols-1 gap-4">
                {activeClientGroupData.orders.map(renderClientOrder)}
              </div>
            ) : (
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.025] px-5 py-12 text-center text-sm text-slate-500">No client orders in this category.</div>
            )}
          </DataPanel>
        </div>
      ) : (
        <section className="grid grid-cols-1 gap-5 xl:grid-cols-[1.05fr_0.95fr]">
          <DataPanel title="Add Supplier Order" eyebrow="Purchase flow" action={<span className="panel-pill">Select supplier and parts</span>}>
            <div className="mb-5 flex flex-wrap gap-2">
              {suppliers.map((supplier) => (
                <button key={supplier} onClick={() => setSelectedSupplier(supplier)} className={`supplier-select ${selectedSupplier === supplier ? "is-active" : ""}`}>
                  {supplier}
                </button>
              ))}
            </div>

            <div className="space-y-3">
              {supplierProducts.map((product) => (
                <div key={product.id} className="supplier-part-row">
                  <div className="min-w-0">
                    <p className="truncate font-bold text-white">{product.name}</p>
                    <p className="mt-1 text-xs text-slate-500">{product.sku} / {product.category}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-black text-orange-200">EUR {product.unitPrice}</span>
                    <button onClick={() => addToCart(product)} className="secondary-action">
                      Add
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </DataPanel>

          <DataPanel title="Supplier Order Basket" eyebrow="Current cart" action={<span className="panel-pill"><ShoppingCart size={13} /> {cart.length} lines</span>}>
            {cart.length ? (
              <div className="space-y-3">
                {cart.map((line) => (
                  <div key={line.productId} className="cart-row">
                    <div className="min-w-0">
                      <p className="truncate font-bold text-white">{line.name}</p>
                      <p className="mt-1 text-xs text-slate-500">{line.sku}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        aria-label={`Quantity for ${line.name}`}
                        className="quantity-input"
                        value={line.quantity}
                        inputMode="numeric"
                        pattern="[0-9]*"
                        onChange={(event) => {
                          const quantity = integerQuantity(event.target.value, line.quantity);
                          setCart((current) => current.map((item) => (item.productId === line.productId ? { ...item, quantity } : item)));
                        }}
                      />
                      <button className="icon-action icon-action--danger" onClick={() => setCart((current) => current.filter((item) => item.productId !== line.productId))} aria-label={`Remove ${line.name}`}>
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                ))}
                <div className="rounded-xl border border-white/[0.08] bg-white/[0.035] p-4">
                  <div className="flex items-center justify-between text-sm"><span className="text-slate-400">Total quantity</span><strong className="text-white">{cart.reduce((sum, item) => sum + item.quantity, 0)}</strong></div>
                  <div className="mt-2 flex items-center justify-between text-sm"><span className="text-slate-400">Estimated value</span><strong className="text-orange-200">EUR {orderTotal(cart).toLocaleString()}</strong></div>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <button className="secondary-action" onClick={() => setCart([])}><RotateCcw size={15} /> Clear cart</button>
                  <button className="primary-button disabled:cursor-not-allowed disabled:opacity-65" onClick={() => void confirmSupplierOrder()} disabled={submittingOrder}>
                    <Check size={16} /> {submittingOrder ? "Confirming..." : "Confirm Order"}
                  </button>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.025] px-5 py-12 text-center text-sm text-slate-500">Select parts from {selectedSupplier} to build a supplier order.</div>
            )}
          </DataPanel>

          <div className="xl:col-span-2">
            <GroupTabs groups={supplierGroups.map(({ id, label, count }) => ({ id, label, count }))} active={activeSupplierGroup} onChange={setActiveSupplierGroup} />
          </div>

          <DataPanel title={activeSupplierGroupData.title} eyebrow={activeSupplierGroupData.eyebrow} className="xl:col-span-2" action={<span className="panel-pill"><PackageCheck size={13} /> {activeSupplierGroupData.count} orders</span>}>
            {activeSupplierGroupData.orders.length ? (
              <div className="space-y-3">
                {activeSupplierGroupData.orders.map(renderSupplierOrder)}
              </div>
            ) : (
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.025] px-5 py-12 text-center text-sm text-slate-500">No supplier orders in this category.</div>
            )}
          </DataPanel>

          <DataPanel title="Supplier Demand Summary" eyebrow="Open and historic purchasing" className="xl:col-span-2" action={<span className="panel-pill"><ShieldCheck size={13} /> {supplierDemandQuantity} parts ordered</span>}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="detail-tile"><span>Needs review</span><strong>{supplierReviewOrders.length}</strong></div>
              <div className="detail-tile"><span>In progress</span><strong>{supplierProgressOrders.length}</strong></div>
              <div className="detail-tile"><span>Received or complete</span><strong>{supplierCompleteOrders.length}</strong></div>
            </div>
          </DataPanel>
        </section>
      )}

      <AnimatePresence>
        {approvalWarning ? (
          <motion.div className="modal-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.section initial={{ opacity: 0, y: 14, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 14, scale: 0.98 }} className="premium-modal">
              <div className="mb-5 flex items-start justify-between gap-4">
                <div>
                  <p className="panel-eyebrow">Stock warning</p>
                  <h2 className="text-xl font-black text-white">Not enough stock to fulfill this order</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    Approving {approvalWarning.order.id} will mark the missing quantities as backorder instead of fully ready stock.
                  </p>
                </div>
                <button aria-label="Close stock warning" onClick={() => setApprovalWarning(null)} className="rounded-lg border border-white/[0.08] p-2 text-slate-400 transition hover:border-orange-300/25 hover:text-orange-200">
                  <X size={16} />
                </button>
              </div>

              <div className="space-y-3">
                {approvalWarning.shortages.map((shortage) => (
                  <div key={`${shortage.productId}-${shortage.sku}`} className="rounded-xl border border-orange-300/20 bg-orange-400/10 p-4">
                    <div className="flex items-start gap-3">
                      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-orange-300/25 bg-orange-400/10 text-orange-200">
                        <TriangleAlert size={17} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-bold text-white">{shortage.name}</p>
                        <p className="mt-1 text-xs text-slate-500">{shortage.sku}</p>
                        <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
                          <div><span className="block text-xs text-slate-500">Requested</span><strong className="text-white">{shortage.requested}</strong></div>
                          <div><span className="block text-xs text-slate-500">Available</span><strong className="text-white">{shortage.available}</strong></div>
                          <div><span className="block text-xs text-slate-500">Missing</span><strong className="text-orange-200">{shortage.missing}</strong></div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                <button className="secondary-action flex-1" onClick={() => setApprovalWarning(null)}>Cancel</button>
                <button className="primary-button flex-1" onClick={() => void confirmBackorderApproval()}>
                  Approve as Backorder
                  <Check size={16} />
                </button>
              </div>
            </motion.section>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}
