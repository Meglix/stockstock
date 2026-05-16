"use client";

import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  CatalogProduct,
  ClientOrder,
  MarketTrend,
  OrderLine,
  SalesSeries,
  StockHealth,
  StockItem,
  SupplierLocation,
  SupplierOrder,
  deriveProductStatus,
  deriveStockStatus,
  recommendedDefaultForCategory,
} from "../data/inventory";

export type DemoNotificationType = "client-order" | "supplier-delivery" | "backorder" | "market";
export type DemoNotificationSeverity = "info" | "warning" | "critical";

export type DemoNotification = {
  id: string;
  type: DemoNotificationType;
  severity: DemoNotificationSeverity;
  title: string;
  message: string;
  createdAt: string;
  read: boolean;
  route: string;
  relatedId?: string;
};

export type ClientOrderAvailabilityShortage = {
  productId: string;
  product_id?: number | string;
  part_id?: number | string;
  name: string;
  part_name?: string;
  sku: string;
  requested: number;
  available: number;
  missing: number;
};

export type ClientOrderAvailabilityPreview = {
  order_id: string;
  can_fulfill: boolean;
  fulfillment_status: string;
  total_requested: number;
  total_allocated: number;
  total_missing: number;
  shortages: ClientOrderAvailabilityShortage[];
};

type BackendNotification = {
  id: string;
  type?: DemoNotificationType;
  severity?: DemoNotificationSeverity;
  title?: string;
  message?: string;
  createdAt?: string;
  created_at?: string;
  read?: boolean;
  route?: string;
  relatedId?: string;
  related_id?: string;
};

type BackendOrderLine = {
  id?: number | string;
  productId?: string | number;
  product_id?: string | number;
  part_id?: number | string;
  sku?: string;
  name?: string;
  part_name?: string;
  quantity?: number;
  allocatedQuantity?: number;
  allocated_quantity?: number;
  shortageQuantity?: number;
  shortage_quantity?: number;
  receivedQuantity?: number;
  received_quantity?: number;
  unitPrice?: number;
  unit_price?: number;
};

type BackendClientOrder = {
  id: string;
  client?: string;
  client_name?: string;
  location?: string;
  items?: BackendOrderLine[];
  requestedTime?: string;
  requested_time?: string;
  status?: ClientOrder["status"];
  fulfillmentStatus?: string;
  fulfillment_status?: string;
  createdAt?: string;
  created_at?: string;
  scheduledFor?: string | null;
  scheduled_for?: string | null;
  stockApplied?: boolean | number;
  stock_applied?: boolean | number;
  shortageQuantity?: number;
  shortage_quantity?: number;
};

type BackendSupplierOrder = {
  id: string;
  supplier?: string;
  supplier_id?: string | null;
  supplier_name?: string;
  location?: string;
  items?: BackendOrderLine[];
  status?: SupplierOrder["status"];
  createdAt?: string;
  created_at?: string;
  estimatedArrival?: string;
  estimated_arrival?: string;
  postponedUntil?: string | null;
  postponed_until?: string | null;
  receivedAt?: string | null;
  received_at?: string | null;
  stockApplied?: boolean | number;
  stock_applied?: boolean | number;
};

type BackendCatalogProduct = {
  id: number | string;
  sku: string;
  part_name: string;
  productId?: string | number;
  product_id?: string | number;
  part_id?: string | number;
  name?: string;
  category?: string | null;
  raw_category?: string | null;
  supplier?: string | null;
  supplier_id?: string | null;
  stock?: number | null;
  current_stock?: number | null;
  recommended?: number | null;
  reorder_point?: number | null;
  optimal_stock?: number | null;
  unitPrice?: number | null;
  unit_price?: number | null;
  status?: CatalogProduct["status"];
  availability?: CatalogProduct["availability"];
  location?: string | null;
  location_id?: string | null;
  display_location?: string | null;
};

type BackendStock = {
  id?: string;
  user_stock_id?: number | string;
  productId?: string | number;
  product_id?: string | number;
  part_id: number | string;
  sku?: string;
  name?: string;
  part_name?: string;
  category?: string;
  raw_category?: string | null;
  supplier?: string | null;
  supplier_id?: string | null;
  location?: string | null;
  location_id?: string | null;
  city?: string | null;
  current?: number | null;
  current_stock?: number | null;
  recommended?: number | null;
  reorderPoint?: number | null;
  reorder_point?: number | null;
  optimal_stock?: number | null;
  status?: StockHealth;
  inventory_status?: StockHealth | string | null;
};

type StockItemInput = Omit<StockItem, "id" | "status"> & { status?: StockHealth };

type DashboardSummary = {
  kpis: {
    total_available_parts: number;
    categories: number;
    pending_client_orders: number;
    pending_supplier_orders: number;
    critical_stock_alerts: number;
  };
  sales_flow: {
    months: string[];
    series: SalesSeries[];
    category_options?: Array<{ category: string; raw_category: string; total_sold: number }>;
    selected_category?: string | null;
  };
  market_trends: MarketTrend[];
  supplier_locations: SupplierLocation[];
  priority_stock: Array<Pick<StockItem, "id" | "name" | "current" | "recommended" | "status">>;
};

type DemoStoreValue = {
  products: CatalogProduct[];
  stockItems: StockItem[];
  clientOrders: ClientOrder[];
  supplierOrders: SupplierOrder[];
  dashboardSummary: DashboardSummary | null;
  dashboardLoading: boolean;
  dashboardError: string | null;
  ordersLoading: boolean;
  ordersError: string | null;
  notifications: DemoNotification[];
  visibleToasts: DemoNotification[];
  unreadCount: number;
  notificationsMuted: boolean;
  refreshDashboardSummary: () => Promise<void>;
  refreshOrderWorkflows: () => Promise<void>;
  addStockItem: (item: StockItemInput) => Promise<void>;
  updateStockItem: (id: string, patch: Partial<StockItemInput>) => Promise<void>;
  deleteStockItem: (id: string) => Promise<void>;
  createSupplierOrder: (supplier: string, lines: OrderLine[]) => Promise<SupplierOrder | undefined>;
  previewClientOrderApproval: (orderId: string) => Promise<ClientOrderAvailabilityPreview>;
  receiveSupplierDelivery: (orderId: string) => Promise<void>;
  postponeSupplierDelivery: (orderId: string, time: string) => Promise<void>;
  refuseSupplierDelivery: (orderId: string) => Promise<void>;
  approveClientOrder: (orderId: string) => Promise<void>;
  completeClientOrder: (orderId: string) => Promise<void>;
  denyClientOrder: (orderId: string) => Promise<void>;
  scheduleClientOrder: (orderId: string, time: string) => Promise<void>;
  markNotificationRead: (id: string) => void;
  markAllNotificationsRead: () => void;
  dismissToast: (id: string) => void;
  toggleNotificationsMuted: () => void;
};

const DemoStoreContext = createContext<DemoStoreValue | null>(null);
const ORDER_REFRESH_INTERVAL_MS = 60_000;

function makeId(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`.toUpperCase();
}

function numericValue(value: unknown, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeApiTimestamp(value: string | null | undefined, fallback = new Date().toISOString()) {
  const timestamp = value?.trim();
  if (!timestamp) return fallback;
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(timestamp);
  const looksLikeIsoDateTime = /^\d{4}-\d{2}-\d{2}T/.test(timestamp);
  return looksLikeIsoDateTime && !hasTimezone ? `${timestamp}Z` : timestamp;
}

function normalizeOptionalApiTimestamp(value: string | null | undefined) {
  return value ? normalizeApiTimestamp(value) : undefined;
}

function normalizeLocalApiTimestamp(value: string | null | undefined) {
  const timestamp = value?.trim();
  if (!timestamp) return undefined;
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(timestamp);
  const looksLikeIsoDateTime = /^\d{4}-\d{2}-\d{2}T/.test(timestamp);
  return looksLikeIsoDateTime && !hasTimezone ? timestamp : normalizeApiTimestamp(timestamp);
}

function localTimezoneOffset(date: Date) {
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const absolute = Math.abs(offset);
  const hours = String(Math.floor(absolute / 60)).padStart(2, "0");
  const minutes = String(absolute % 60).padStart(2, "0");
  return `${sign}${hours}:${minutes}`;
}

function localClockTimestamp(time: string) {
  const [hoursText, minutesText] = time.split(":");
  const hours = Number(hoursText);
  const minutes = Number(minutesText);
  const date = new Date();

  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return undefined;

  date.setHours(hours, minutes, 0, 0);
  if (date.getTime() <= Date.now()) date.setDate(date.getDate() + 1);

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const normalizedHours = String(date.getHours()).padStart(2, "0");
  const normalizedMinutes = String(date.getMinutes()).padStart(2, "0");

  return `${year}-${month}-${day}T${normalizedHours}:${normalizedMinutes}:00${localTimezoneOffset(date)}`;
}

function formatApiError(error: unknown) {
  return error instanceof Error ? error.message : "Backend request failed.";
}

function getAuthToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("auth_token");
}

function getStoredUser() {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(window.localStorage.getItem("auth_user") || "null") as {
      role?: string;
      role_name?: string;
      location?: string | null;
      location_id?: string | null;
      user_locations?: string[] | null;
      user_location_ids?: string[] | null;
    } | null;
  } catch {
    return null;
  }
}

function isCurrentUserScoped() {
  const user = getStoredUser();
  return (user?.role_name ?? user?.role) === "user";
}

function currentOrderLocation() {
  const user = getStoredUser();
  return user?.user_location_ids?.find(Boolean) || user?.location_id || user?.user_locations?.find(Boolean) || user?.location || undefined;
}

function apiErrorMessage(status: number, detail: unknown) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") return item.msg;
        return JSON.stringify(item);
      })
      .join("; ");
  }
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  return `Request failed (${status}).`;
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getAuthToken();

  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(path, { ...init, headers });
  const data = await response.json().catch(() => undefined);

  if (!response.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? data.detail : undefined;
    throw new Error(apiErrorMessage(response.status, detail));
  }

  return data as T;
}

function upsertById<T extends { id: string }>(items: T[], updated: T) {
  if (items.some((item) => item.id === updated.id)) {
    return items.map((item) => (item.id === updated.id ? updated : item));
  }
  return [updated, ...items];
}

function normalizeBackendLine(line: BackendOrderLine): OrderLine {
  return {
    productId: String(line.productId ?? line.product_id ?? line.part_id ?? line.id ?? ""),
    name: line.name ?? line.part_name ?? "Unknown part",
    sku: line.sku ?? "",
    quantity: numericValue(line.quantity, 0),
    unitPrice: numericValue(line.unitPrice ?? line.unit_price, 0),
    allocatedQuantity: numericValue(line.allocatedQuantity ?? line.allocated_quantity, 0),
    shortageQuantity: numericValue(line.shortageQuantity ?? line.shortage_quantity, 0),
    receivedQuantity: numericValue(line.receivedQuantity ?? line.received_quantity, 0),
  };
}

function normalizeClientOrder(order: BackendClientOrder): ClientOrder {
  return {
    id: order.id,
    client: order.client ?? order.client_name ?? "Client",
    items: Array.isArray(order.items) ? order.items.map(normalizeBackendLine) : [],
    requestedTime: order.requestedTime ?? order.requested_time ?? "",
    status: order.status ?? "Pending",
    createdAt: normalizeApiTimestamp(order.createdAt ?? order.created_at),
    location: order.location,
    scheduledFor: normalizeLocalApiTimestamp(order.scheduledFor ?? order.scheduled_for),
    stockApplied: Boolean(order.stockApplied ?? order.stock_applied),
    fulfillmentStatus: order.fulfillmentStatus ?? order.fulfillment_status,
    shortageQuantity: numericValue(order.shortageQuantity ?? order.shortage_quantity, 0),
  };
}

function normalizeSupplierOrder(order: BackendSupplierOrder): SupplierOrder {
  return {
    id: order.id,
    supplier: order.supplier ?? order.supplier_name ?? order.supplier_id ?? "Supplier",
    supplierId: order.supplier_id ?? undefined,
    items: Array.isArray(order.items) ? order.items.map(normalizeBackendLine) : [],
    status: order.status ?? "Pending",
    createdAt: normalizeApiTimestamp(order.createdAt ?? order.created_at),
    location: order.location,
    estimatedArrival: normalizeApiTimestamp(order.estimatedArrival ?? order.estimated_arrival, "Pending confirmation"),
    postponedUntil: normalizeLocalApiTimestamp(order.postponedUntil ?? order.postponed_until),
    receivedAt: normalizeOptionalApiTimestamp(order.receivedAt ?? order.received_at),
    stockApplied: Boolean(order.stockApplied ?? order.stock_applied),
  };
}

function isCatalogStatus(value: unknown): value is CatalogProduct["status"] {
  return ["In Stock", "Low Stock", "Critical", "Overstock", "Order Only", "Not Available"].includes(String(value));
}

function isStockStatus(value: unknown): value is StockHealth {
  return ["Healthy", "Low Stock", "Critical", "Reorder Soon", "Overstock"].includes(String(value));
}

function normalizeCatalogProduct(item: BackendCatalogProduct): CatalogProduct {
  const id = String(item.productId ?? item.product_id ?? item.part_id ?? item.id);
  const stock = numericValue(item.stock ?? item.current_stock, 0);
  const category = item.category ?? item.raw_category ?? "Uncategorized";
  const categoryDefault = recommendedDefaultForCategory(category);
  const rawRecommended = item.recommended ?? item.optimal_stock ?? item.reorder_point;
  const recommended = rawRecommended == null ? categoryDefault : Math.max(numericValue(rawRecommended, categoryDefault), 1);
  const reorderPoint = numericValue(item.reorder_point, 0);
  const availability: CatalogProduct["availability"] =
    item.availability === "available" || item.availability === "order-only" ? item.availability : stock > 0 ? "available" : "order-only";

  return {
    id,
    name: item.name ?? item.part_name,
    sku: item.sku,
    category,
    supplier: item.supplier ?? item.supplier_id ?? "Unknown Supplier",
    supplierId: item.supplier_id ?? undefined,
    location: item.location ?? item.display_location ?? undefined,
    locationId: item.location_id ?? undefined,
    stock,
    recommended,
    reorderPoint,
    unitPrice: numericValue(item.unitPrice ?? item.unit_price, 0),
    status: isCatalogStatus(item.status) ? item.status : deriveProductStatus(stock, availability, recommended),
    availability,
  };
}

function normalizeBackendStockItem(row: BackendStock): StockItem {
  const productId = String(row.productId ?? row.product_id ?? row.part_id);
  const current = numericValue(row.current ?? row.current_stock, 0);
  const category = row.category ?? row.raw_category ?? "Uncategorized";
  const rawRecommended = row.recommended ?? row.optimal_stock ?? row.reorderPoint ?? row.reorder_point;
  const recommended = rawRecommended == null ? recommendedDefaultForCategory(category) : Math.max(numericValue(rawRecommended, recommendedDefaultForCategory(category)), 1);
  const reorderPoint = numericValue(row.reorderPoint ?? row.reorder_point, 0);
  const location = row.location_id ?? row.location ?? row.city ?? "My Store";

  return {
    id: String(row.id ?? `stock-${productId}-${location}`),
    productId,
    name: row.name ?? row.part_name ?? row.sku ?? "Unknown part",
    sku: row.sku ?? "",
    category,
    supplier: row.supplier ?? row.supplier_id ?? "Unknown Supplier",
    current,
    recommended,
    reorderPoint,
    status: deriveStockStatus(current, recommended, reorderPoint),
    location,
    locationId: row.location_id ?? undefined,
  };
}

function isNotificationType(value: unknown): value is DemoNotificationType {
  return ["client-order", "supplier-delivery", "backorder", "market"].includes(String(value));
}

function isNotificationSeverity(value: unknown): value is DemoNotificationSeverity {
  return ["info", "warning", "critical"].includes(String(value));
}

function normalizeBackendNotification(notification: BackendNotification): DemoNotification {
  return {
    id: String(notification.id),
    type: isNotificationType(notification.type) ? notification.type : "market",
    severity: isNotificationSeverity(notification.severity) ? notification.severity : "info",
    title: notification.title ?? "Notification",
    message: notification.message ?? "",
    createdAt: normalizeApiTimestamp(notification.createdAt ?? notification.created_at),
    read: Boolean(notification.read),
    route: notification.route ?? "/dashboard",
    relatedId: notification.relatedId ?? notification.related_id,
  };
}

function mergeBackendNotifications(current: DemoNotification[], backendNotifications: DemoNotification[], suppressedOrderIds = new Set<string>()) {
  const currentById = new Map(current.map((notification) => [notification.id, notification]));
  return backendNotifications
    .filter((notification) => notification.type === "backorder" || !notification.relatedId || !suppressedOrderIds.has(notification.relatedId))
    .map((notification) => ({
      ...notification,
      read: currentById.get(notification.id)?.read ?? notification.read,
    }));
}

function stockPayload(item: StockItemInput) {
  const partId = Number(item.productId);
  return {
    ...(Number.isFinite(partId) ? { part_id: partId } : { sku: item.sku }),
    sku: item.sku,
    name: item.name,
    category: item.category,
    supplier: item.supplier,
    location: item.location,
    location_id: item.locationId,
    current_stock: item.current,
    optimal_stock: item.recommended,
    reorder_point: item.reorderPoint,
  };
}

function stockUpdatePayload(item: StockItemInput) {
  return {
    current_stock: item.current,
    optimal_stock: item.recommended,
    reorder_point: item.reorderPoint,
  };
}

function supplierOrderPayload(lines: OrderLine[]) {
  return {
    location: currentOrderLocation() || lines.find((line) => line.location)?.location,
    estimated_arrival: "Pending confirmation",
    items: lines.map((line) => {
      const partId = Number(line.productId);
      if (Number.isFinite(partId)) return { part_id: partId, quantity: line.quantity };
      return { sku: line.sku, quantity: line.quantity };
    }),
  };
}

export function DemoStoreProvider({ children }: { children: ReactNode }) {
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [stockItems, setStockItems] = useState<StockItem[]>([]);
  const [clientOrders, setClientOrders] = useState<ClientOrder[]>([]);
  const [supplierOrders, setSupplierOrders] = useState<SupplierOrder[]>([]);
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<DemoNotification[]>([]);
  const [visibleToastIds, setVisibleToastIds] = useState<string[]>([]);
  const [notificationsMuted, setNotificationsMuted] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("rrparts_notifications_muted") === "true";
  });
  const notificationsLoadedRef = useRef(false);
  const notificationsRef = useRef<DemoNotification[]>([]);
  const suppressedOrderNotificationIdsRef = useRef<Set<string>>(new Set());

  const showToastIds = useCallback((ids: string[]) => {
    if (notificationsMuted) return;
    if (!ids.length) return;
    setVisibleToastIds((current) => [...ids, ...current.filter((id) => !ids.includes(id))].slice(0, 4));
    ids.forEach((id) => {
      window.setTimeout(() => {
        setVisibleToastIds((current) => current.filter((toastId) => toastId !== id));
      }, 10000);
    });
  }, [notificationsMuted]);

  const pushNotification = useCallback((notification: Omit<DemoNotification, "id" | "createdAt" | "read">) => {
    const next: DemoNotification = {
      ...notification,
      id: makeId("NT"),
      createdAt: new Date().toISOString(),
      read: false,
    };

    setNotifications((current) => [next, ...current].slice(0, 24));
    showToastIds([next.id]);
  }, [showToastIds]);

  const clearOrderNotifications = useCallback((orderId: string) => {
    suppressedOrderNotificationIdsRef.current.add(orderId);
    const matchingIds = notificationsRef.current.filter((notification) => notification.relatedId === orderId).map((notification) => notification.id);
    setNotifications((current) => {
      const next = current.filter((notification) => notification.relatedId !== orderId);
      notificationsRef.current = next;
      return next;
    });
    if (matchingIds.length) {
      setVisibleToastIds((current) => current.filter((toastId) => !matchingIds.includes(toastId)));
    }
  }, []);

  const loadBackendCatalog = useCallback(async () => {
    if (!getAuthToken()) return;

    try {
      const [catalog, stockRows] = await Promise.all([apiRequest<BackendCatalogProduct[]>("/api/parts/catalog"), apiRequest<BackendStock[]>("/api/stock")]);
      setProducts(catalog.map(normalizeCatalogProduct));
      const visibleStockRows = isCurrentUserScoped() ? stockRows.filter((row) => row.user_stock_id || String(row.id ?? "").startsWith("user-stock-")) : stockRows;
      setStockItems(visibleStockRows.map(normalizeBackendStockItem));
    } catch (error) {
      console.warn("Could not load backend catalog", error);
    }
  }, []);

  const refreshDashboardSummary = useCallback(async () => {
    if (!getAuthToken()) return;

    setDashboardLoading(true);
    try {
      const summary = await apiRequest<DashboardSummary>("/api/dashboard/summary");
      setDashboardSummary(summary);
      setDashboardError(null);
    } catch (error) {
      setDashboardError(formatApiError(error));
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  const refreshNotifications = useCallback(async (options?: { allowGeneration?: boolean }) => {
    if (!getAuthToken()) return;

    try {
      const rows = await apiRequest<BackendNotification[]>(`/api/notifications${options?.allowGeneration ? "?generate=true" : ""}`);
      const nextNotifications = rows.map(normalizeBackendNotification);
      const currentIds = new Set(notificationsRef.current.map((notification) => notification.id));
      const toastIds = notificationsLoadedRef.current
        ? nextNotifications
            .filter(
              (notification) =>
                !currentIds.has(notification.id) &&
                !notification.read &&
                (notification.type === "backorder" || !notification.relatedId || !suppressedOrderNotificationIdsRef.current.has(notification.relatedId)),
            )
            .slice(0, 4)
            .map((notification) => notification.id)
        : [];
      notificationsLoadedRef.current = true;
      setNotifications((current) => {
        const merged = mergeBackendNotifications(current, nextNotifications, suppressedOrderNotificationIdsRef.current);
        notificationsRef.current = merged;
        return merged;
      });
      showToastIds(toastIds);
    } catch (error) {
      console.warn("Could not load backend notifications", error);
    }
  }, [showToastIds]);

  const refreshOrderWorkflows = useCallback(async () => {
    if (!getAuthToken()) return;

    setOrdersLoading(true);
    try {
      const [clients, suppliers] = await Promise.all([
        apiRequest<BackendClientOrder[]>("/api/orders/clients"),
        apiRequest<BackendSupplierOrder[]>("/api/orders/suppliers"),
      ]);
      const nextClientOrders = clients.map(normalizeClientOrder);
      const nextSupplierOrders = suppliers.map(normalizeSupplierOrder);
      setClientOrders(nextClientOrders);
      setSupplierOrders(nextSupplierOrders);
      setOrdersError(null);
    } catch (error) {
      setOrdersError(formatApiError(error));
    } finally {
      setOrdersLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBackendCatalog();
    void refreshDashboardSummary();
    void refreshOrderWorkflows();
    void refreshNotifications();
  }, [loadBackendCatalog, refreshDashboardSummary, refreshNotifications, refreshOrderWorkflows]);

  useEffect(() => {
    notificationsRef.current = notifications;
  }, [notifications]);

  useEffect(() => {
    localStorage.setItem("rrparts_notifications_muted", String(notificationsMuted));
    if (notificationsMuted) setVisibleToastIds([]);
  }, [notificationsMuted]);

  useEffect(() => {
    if (!getAuthToken()) return;

    const intervalId = window.setInterval(() => {
      void refreshNotifications({ allowGeneration: true }).then(() => {
        void refreshOrderWorkflows();
        void refreshDashboardSummary();
      });
    }, ORDER_REFRESH_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [refreshDashboardSummary, refreshNotifications, refreshOrderWorkflows]);

  const notifyOrderFailure = useCallback(
    (title: string, error: unknown) => {
      const message = formatApiError(error);
      setOrdersError(message);
      pushNotification({
        type: "market",
        severity: "warning",
        title,
        message,
        route: "/dashboard/orders",
      });
    },
    [pushNotification],
  );

  const previewClientOrderApproval = useCallback(async (orderId: string) => {
    return apiRequest<ClientOrderAvailabilityPreview>(`/api/orders/clients/${encodeURIComponent(orderId)}/availability`);
  }, []);

  const addStockItem = useCallback(
    async (item: StockItemInput) => {
      try {
        const saved = await apiRequest<BackendStock>("/api/stock", {
          method: "POST",
          body: JSON.stringify(stockPayload(item)),
        });
        const next = normalizeBackendStockItem(saved);
        setStockItems((current) => upsertById(current, next));
        void loadBackendCatalog();
        void refreshDashboardSummary();
      } catch (error) {
        notifyOrderFailure("Stock add failed", error);
        throw error;
      }
    },
    [loadBackendCatalog, notifyOrderFailure, refreshDashboardSummary],
  );

  const updateStockItem = useCallback(
    async (id: string, patch: Partial<StockItemInput>) => {
      const existing = stockItems.find((item) => item.id === id);
      if (!existing) return;

      const updated = { ...existing, ...patch };
      try {
        const saved = await apiRequest<BackendStock>(`/api/stock/${encodeURIComponent(existing.productId)}/${encodeURIComponent(existing.locationId ?? existing.location)}`, {
          method: "PATCH",
          body: JSON.stringify(stockUpdatePayload(updated)),
        });
        const next = normalizeBackendStockItem(saved);
        setStockItems((current) => current.map((item) => (item.id === id ? next : item)));
        void loadBackendCatalog();
        void refreshDashboardSummary();
      } catch (error) {
        notifyOrderFailure("Stock update failed", error);
        throw error;
      }
    },
    [loadBackendCatalog, notifyOrderFailure, refreshDashboardSummary, stockItems],
  );

  const deleteStockItem = useCallback(
    async (id: string) => {
      const existing = stockItems.find((item) => item.id === id);
      if (!existing) return;

      try {
        await apiRequest<{ message: string }>(`/api/stock/${encodeURIComponent(existing.productId)}/${encodeURIComponent(existing.locationId ?? existing.location)}`, {
          method: "DELETE",
        });
        setStockItems((current) => current.filter((item) => item.id !== id));
        void loadBackendCatalog();
        void refreshDashboardSummary();
      } catch (error) {
        notifyOrderFailure("Stock delete failed", error);
        throw error;
      }
    },
    [loadBackendCatalog, notifyOrderFailure, refreshDashboardSummary, stockItems],
  );

  const createSupplierOrder = useCallback(
    async (supplier: string, lines: OrderLine[]) => {
      if (!lines.length) return undefined;

      try {
        const created = await apiRequest<BackendSupplierOrder>("/api/orders/suppliers", {
          method: "POST",
          body: JSON.stringify(supplierOrderPayload(lines)),
        });
        const order = normalizeSupplierOrder(created);
        setSupplierOrders((current) => upsertById(current, order));
        void refreshOrderWorkflows();
        void refreshDashboardSummary();
        return order;
      } catch (error) {
        notifyOrderFailure("Supplier order failed", error);
        return undefined;
      }
    },
    [notifyOrderFailure, refreshDashboardSummary, refreshOrderWorkflows],
  );

  const receiveSupplierDelivery = useCallback(
    async (orderId: string) => {
      try {
        const updated = await apiRequest<BackendSupplierOrder>(`/api/orders/suppliers/${orderId}/receive`, { method: "POST" });
        setSupplierOrders((current) => upsertById(current, normalizeSupplierOrder(updated)));
        clearOrderNotifications(orderId);
        await loadBackendCatalog();
        await refreshDashboardSummary();
        await refreshOrderWorkflows();
      } catch (error) {
        notifyOrderFailure("Supplier receive failed", error);
      }
    },
    [clearOrderNotifications, loadBackendCatalog, notifyOrderFailure, refreshDashboardSummary, refreshOrderWorkflows],
  );

  const postponeSupplierDelivery = useCallback(
    async (orderId: string, time: string) => {
      try {
        const updated = await apiRequest<BackendSupplierOrder>(`/api/orders/suppliers/${orderId}/postpone`, {
          method: "POST",
          body: JSON.stringify({ postponed_until: localClockTimestamp(time) ?? undefined, time }),
        });
        setSupplierOrders((current) => upsertById(current, normalizeSupplierOrder(updated)));
        clearOrderNotifications(orderId);
        void refreshDashboardSummary();
        void refreshOrderWorkflows();
      } catch (error) {
        notifyOrderFailure("Supplier postpone failed", error);
      }
    },
    [clearOrderNotifications, notifyOrderFailure, refreshDashboardSummary, refreshOrderWorkflows],
  );

  const refuseSupplierDelivery = useCallback(
    async (orderId: string) => {
      try {
        const updated = await apiRequest<BackendSupplierOrder>(`/api/orders/suppliers/${orderId}/refuse`, { method: "POST" });
        setSupplierOrders((current) => upsertById(current, normalizeSupplierOrder(updated)));
        clearOrderNotifications(orderId);
        void refreshDashboardSummary();
        void refreshOrderWorkflows();
      } catch (error) {
        notifyOrderFailure("Supplier refuse failed", error);
      }
    },
    [clearOrderNotifications, notifyOrderFailure, refreshDashboardSummary, refreshOrderWorkflows],
  );

  const approveClientOrder = useCallback(
    async (orderId: string) => {
      try {
        const updated = await apiRequest<BackendClientOrder>(`/api/orders/clients/${orderId}/approve`, { method: "POST" });
        setClientOrders((current) => upsertById(current, normalizeClientOrder(updated)));
        clearOrderNotifications(orderId);
        void loadBackendCatalog();
        void refreshDashboardSummary();
        void refreshOrderWorkflows();
      } catch (error) {
        notifyOrderFailure("Client approval failed", error);
      }
    },
    [clearOrderNotifications, loadBackendCatalog, notifyOrderFailure, refreshDashboardSummary, refreshOrderWorkflows],
  );

  const completeClientOrder = useCallback(
    async (orderId: string) => {
      try {
        const updated = await apiRequest<BackendClientOrder>(`/api/orders/clients/${orderId}/complete`, { method: "POST" });
        setClientOrders((current) => upsertById(current, normalizeClientOrder(updated)));
        clearOrderNotifications(orderId);
        void refreshDashboardSummary();
        void refreshOrderWorkflows();
      } catch (error) {
        notifyOrderFailure("Client completion failed", error);
      }
    },
    [clearOrderNotifications, notifyOrderFailure, refreshDashboardSummary, refreshOrderWorkflows],
  );

  const denyClientOrder = useCallback(
    async (orderId: string) => {
      try {
        const updated = await apiRequest<BackendClientOrder>(`/api/orders/clients/${orderId}/deny`, { method: "POST" });
        setClientOrders((current) => upsertById(current, normalizeClientOrder(updated)));
        clearOrderNotifications(orderId);
        void refreshDashboardSummary();
        void refreshOrderWorkflows();
      } catch (error) {
        notifyOrderFailure("Client refusal failed", error);
      }
    },
    [clearOrderNotifications, notifyOrderFailure, refreshDashboardSummary, refreshOrderWorkflows],
  );

  const scheduleClientOrder = useCallback(
    async (orderId: string, time: string) => {
      try {
        const updated = await apiRequest<BackendClientOrder>(`/api/orders/clients/${orderId}/schedule`, {
          method: "POST",
          body: JSON.stringify({ scheduled_for: localClockTimestamp(time) ?? undefined, time }),
        });
        setClientOrders((current) => upsertById(current, normalizeClientOrder(updated)));
        clearOrderNotifications(orderId);
        void refreshDashboardSummary();
        void refreshOrderWorkflows();
      } catch (error) {
        notifyOrderFailure("Client scheduling failed", error);
      }
    },
    [clearOrderNotifications, notifyOrderFailure, refreshDashboardSummary, refreshOrderWorkflows],
  );

  const markNotificationRead = useCallback((id: string) => {
    setNotifications((current) => current.map((notification) => (notification.id === id ? { ...notification, read: true } : notification)));
  }, []);

  const markAllNotificationsRead = useCallback(() => {
    setNotifications((current) => current.map((notification) => ({ ...notification, read: true })));
  }, []);

  const dismissToast = useCallback((id: string) => {
    setVisibleToastIds((current) => current.filter((toastId) => toastId !== id));
  }, []);

  const toggleNotificationsMuted = useCallback(() => {
    setNotificationsMuted((current) => !current);
  }, []);

  const visibleToasts = useMemo(
    () => (notificationsMuted ? [] : visibleToastIds.map((id) => notifications.find((notification) => notification.id === id)).filter((item): item is DemoNotification => Boolean(item))),
    [notifications, notificationsMuted, visibleToastIds],
  );

  const value = useMemo<DemoStoreValue>(
    () => ({
      products,
      stockItems,
      clientOrders,
      supplierOrders,
      dashboardSummary,
      dashboardLoading,
      dashboardError,
      ordersLoading,
      ordersError,
      notifications,
      visibleToasts,
      unreadCount: notifications.filter((notification) => !notification.read).length,
      notificationsMuted,
      refreshDashboardSummary,
      refreshOrderWorkflows,
      addStockItem,
      updateStockItem,
      deleteStockItem,
      createSupplierOrder,
      previewClientOrderApproval,
      receiveSupplierDelivery,
      postponeSupplierDelivery,
      refuseSupplierDelivery,
      approveClientOrder,
      completeClientOrder,
      denyClientOrder,
      scheduleClientOrder,
      markNotificationRead,
      markAllNotificationsRead,
      dismissToast,
      toggleNotificationsMuted,
    }),
    [
      addStockItem,
      approveClientOrder,
      clientOrders,
      completeClientOrder,
      createSupplierOrder,
      dashboardError,
      dashboardLoading,
      dashboardSummary,
      deleteStockItem,
      denyClientOrder,
      dismissToast,
      markAllNotificationsRead,
      markNotificationRead,
      notifications,
      notificationsMuted,
      ordersError,
      ordersLoading,
      postponeSupplierDelivery,
      previewClientOrderApproval,
      products,
      receiveSupplierDelivery,
      refreshDashboardSummary,
      refreshOrderWorkflows,
      refuseSupplierDelivery,
      scheduleClientOrder,
      stockItems,
      supplierOrders,
      updateStockItem,
      visibleToasts,
      toggleNotificationsMuted,
    ],
  );

  return <DemoStoreContext.Provider value={value}>{children}</DemoStoreContext.Provider>;
}

export function useDemoStore() {
  const context = useContext(DemoStoreContext);
  if (!context) {
    throw new Error("useDemoStore must be used inside DemoStoreProvider");
  }
  return context;
}
