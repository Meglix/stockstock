import {
  AlertTriangle,
  BadgeCheck,
  Boxes,
  ClipboardList,
  Gauge,
  LayoutGrid,
  Package,
  ShieldCheck,
  Timer,
  Truck,
} from "lucide-react";

export type PartStatus = "In Stock" | "Low Stock" | "Critical" | "Overstock" | "Order Only" | "Not Available";
export type StockHealth = "Healthy" | "Low Stock" | "Critical" | "Reorder Soon" | "Overstock";
export type SupplierOrderStatus = "Pending" | "Approved" | "Delivered" | "Delayed" | "Refused" | "Received";
export type ClientOrderStatus = "Pending" | "Approved" | "Denied" | "Scheduled" | "Delivered";
export type OrderStatus = SupplierOrderStatus | ClientOrderStatus;

export type CatalogProduct = {
  id: string;
  name: string;
  sku: string;
  category: string;
  supplier: string;
  supplierId?: string;
  location?: string;
  locationId?: string;
  stock: number;
  recommended?: number;
  reorderPoint?: number;
  unitPrice: number;
  status: PartStatus;
  availability: "available" | "order-only";
};

export type StockItem = {
  id: string;
  productId: string;
  name: string;
  sku: string;
  category: string;
  supplier: string;
  current: number;
  recommended: number;
  reorderPoint: number;
  status: StockHealth;
  location: string;
  locationId?: string;
};

export type OrderLine = {
  productId: string;
  name: string;
  sku: string;
  quantity: number;
  unitPrice: number;
  location?: string;
  allocatedQuantity?: number;
  shortageQuantity?: number;
  receivedQuantity?: number;
};

export type ClientOrder = {
  id: string;
  client: string;
  items: OrderLine[];
  requestedTime: string;
  status: ClientOrderStatus;
  createdAt: string;
  location?: string;
  scheduledFor?: string;
  stockApplied?: boolean;
  fulfillmentStatus?: string;
  shortageQuantity?: number;
};

export type SupplierOrder = {
  id: string;
  supplier: string;
  supplierId?: string;
  items: OrderLine[];
  status: SupplierOrderStatus;
  createdAt: string;
  location?: string;
  estimatedArrival: string;
  receivedAt?: string;
  postponedUntil?: string;
  stockApplied?: boolean;
};

export type MarketTrend = {
  id: string;
  title: string;
  detail: string;
  priority: "High" | "Medium" | "Stable" | "Declining";
  category: string;
};

export type SupplierLocation = {
  supplier: string;
  country: string;
  country_code?: string;
  city: string;
  parts: number;
  catalog_parts?: number;
  available_units?: number;
  x: number;
  y: number;
};

export type SalesSeries = {
  category: string;
  raw_category?: string;
  total_sold?: number;
  color: string;
  values: number[];
};

const nowIso = () => new Date().toISOString();

export function stockTarget(optimalStock: number, reorderPoint = 0) {
  return Math.max(optimalStock, reorderPoint, 1);
}

const categoryRecommendedDefaults: Record<string, number> = {
  tires: 35,
  battery: 20,
  batteries: 20,
  brakes: 25,
  filters: 30,
  wipers: 20,
  fluids: 40,
  "winter fluids": 40,
  winter_fluids: 40,
  coolant: 40,
  lighting: 15,
  maintenance: 25,
  accessories: 20,
  "ac cooling": 20,
  ac_cooling: 20,
  "air conditioning": 20,
};

export function recommendedDefaultForCategory(category: string | undefined | null) {
  const normalized = (category ?? "").trim().toLowerCase().replace(/-/g, " ");
  return categoryRecommendedDefaults[normalized] ?? categoryRecommendedDefaults[normalized.replace(/\s+/g, "_")] ?? 20;
}

export function deriveStockStatus(current: number, optimalStock: number, reorderPoint = 0): StockHealth {
  const target = stockTarget(optimalStock, reorderPoint);
  const coverage = current / target;
  if (current <= 0 || coverage < 0.35) return "Critical";
  if (coverage < 0.6) return "Low Stock";
  if (coverage < 0.8) return "Reorder Soon";
  if (coverage >= 1.45) return "Overstock";
  return "Healthy";
}

export function deriveProductStatus(stock: number, availability: CatalogProduct["availability"], recommended = 90): PartStatus {
  if (availability === "order-only") return "Order Only";
  const stockStatus = deriveStockStatus(stock, recommended);
  if (stockStatus === "Healthy" || stockStatus === "Reorder Soon") return "In Stock";
  if (stockStatus === "Overstock") return "Overstock";
  return stockStatus;
}

export function stockStatusDescription(status: string, current: number, optimalStock: number, reorderPoint = 0, reserved = 0) {
  const target = stockTarget(optimalStock, reorderPoint);
  const coverage = Math.round((current / target) * 100);
  const base = (() => {
    if (status === "Critical") return `Available stock is ${current}, below the reorder threshold ${reorderPoint}.`;
    if (status === "Low Stock") return `Available stock is ${coverage}% of the backend target ${target}.`;
    if (status === "Reorder Soon") return `Available stock is close to the backend target ${target}; plan replenishment soon.`;
    if (status === "Overstock") return `Available stock is ${current}, above the overstock threshold ${Math.ceil(target * 1.45)}.`;
    if (status === "Healthy" || status === "In Stock") return `Available stock is between reorder threshold ${reorderPoint} and overstock threshold ${Math.ceil(target * 1.45)}.`;
    if (status === "Order Only") return "No local stock is currently available; order it from the supplier.";
    return "";
  })();

  if (reserved > 0) return `${base} ${reserved} units are reserved for approved client backorders.`;
  return base;
}

export const dashboardKpis = [
  {
    label: "Total Available Parts",
    value: "12,480",
    detail: "+4.8% inventory coverage",
    icon: Package,
    tone: "orange",
  },
  {
    label: "Categories",
    value: "32",
    detail: "5 high velocity groups",
    icon: LayoutGrid,
    tone: "steel",
  },
  {
    label: "Active Suppliers",
    value: "18",
    detail: "Across 5 key regions",
    icon: Truck,
    tone: "green",
  },
  {
    label: "Pending Orders",
    value: "46",
    detail: "9 need approval today",
    icon: ClipboardList,
    tone: "purple",
  },
] as const;

export const initialProducts: CatalogProduct[] = [
  {
    id: "brake-pads-208",
    name: "Brake Pads Peugeot 208",
    sku: "PEU-208-BRK",
    category: "Brakes",
    supplier: "Bosch",
    stock: 84,
    unitPrice: 48,
    status: "In Stock",
    availability: "available",
  },
  {
    id: "winter-tires-205",
    name: "Winter Tires 205/55 R16",
    sku: "TYR-WIN-205",
    category: "Tires",
    supplier: "Michelin",
    stock: 42,
    unitPrice: 92,
    status: "Low Stock",
    availability: "available",
  },
  {
    id: "oil-filter-2008",
    name: "Oil Filter Peugeot 2008",
    sku: "PEU-2008-OIL",
    category: "Filters",
    supplier: "Valeo",
    stock: 210,
    unitPrice: 18,
    status: "Overstock",
    availability: "available",
  },
  {
    id: "timing-belt-3008",
    name: "Timing Belt Peugeot 3008",
    sku: "PEU-3008-TMG",
    category: "Engine Parts",
    supplier: "Continental",
    stock: 25,
    unitPrice: 76,
    status: "Critical",
    availability: "available",
  },
  {
    id: "wiper-blades-universal",
    name: "Wiper Blades Universal",
    sku: "WIP-UNI-22",
    category: "Accessories",
    supplier: "Peugeot OEM",
    stock: 96,
    unitPrice: 22,
    status: "In Stock",
    availability: "available",
  },
  {
    id: "abs-sensor-front",
    name: "ABS Sensor Front",
    sku: "ABS-FRT-018",
    category: "Electronics",
    supplier: "Bosch",
    stock: 19,
    unitPrice: 64,
    status: "Low Stock",
    availability: "available",
  },
  {
    id: "car-stickers-premium",
    name: "Car Stickers Premium Pack",
    sku: "ACC-STK-PRM",
    category: "Accessories",
    supplier: "Valeo",
    stock: 0,
    unitPrice: 14,
    status: "Order Only",
    availability: "order-only",
  },
  {
    id: "led-headlight-unit",
    name: "LED Headlight Unit",
    sku: "LED-HDL-900",
    category: "Electronics",
    supplier: "Peugeot OEM",
    stock: 0,
    unitPrice: 240,
    status: "Order Only",
    availability: "order-only",
  },
  {
    id: "battery-12v-premium",
    name: "Battery 12V Premium",
    sku: "BAT-12V-PRM",
    category: "Batteries",
    supplier: "Bosch",
    stock: 68,
    unitPrice: 118,
    status: "In Stock",
    availability: "available",
  },
  {
    id: "coolant-antifreeze",
    name: "Coolant Antifreeze",
    sku: "CLT-AFR-5L",
    category: "Fluids",
    supplier: "Marelli",
    stock: 145,
    unitPrice: 26,
    status: "In Stock",
    availability: "available",
  },
  {
    id: "engine-oil-5w30",
    name: "Engine Oil 5W30",
    sku: "OIL-5W30-5L",
    category: "Fluids",
    supplier: "Peugeot OEM",
    stock: 31,
    unitPrice: 42,
    status: "Critical",
    availability: "available",
  },
];

export const initialStockItems: StockItem[] = initialProducts
  .filter((product) => product.availability === "available")
  .map((product) => {
    const recommended = product.id === "oil-filter-2008" ? 125 : product.id === "coolant-antifreeze" ? 110 : 90;
    return {
      id: `stock-${product.id}`,
      productId: product.id,
      name: product.name,
      sku: product.sku,
      category: product.category,
      supplier: product.supplier,
      current: product.stock,
      recommended,
      reorderPoint: Math.round(recommended * 0.42),
      status: deriveStockStatus(product.stock, recommended),
      location: "My Store",
    };
  });

export const supplierInventory = [
  { supplier: "Bosch", parts: 2850, country: "Germany", badge: "DE" },
  { supplier: "Valeo", parts: 1920, country: "France", badge: "FR" },
  { supplier: "Continental", parts: 1640, country: "Germany", badge: "DE" },
  { supplier: "Michelin", parts: 1250, country: "France", badge: "FR" },
  { supplier: "Peugeot OEM", parts: 3100, country: "France", badge: "OEM" },
];

export const supplierLocations: SupplierLocation[] = [
  { supplier: "Valeo", country: "France", country_code: "FR", city: "Paris", parts: 6, available_units: 1920, x: 507, y: 114 },
  { supplier: "Bosch", country: "Germany", country_code: "DE", city: "Stuttgart", parts: 8, available_units: 2850, x: 525, y: 115 },
  { supplier: "Marelli", country: "Italy", country_code: "IT", city: "Milan", parts: 3, available_units: 980, x: 526, y: 124 },
  { supplier: "RRParts Hub", country: "Romania", country_code: "RO", city: "Bucharest", parts: 5, available_units: 760, x: 573, y: 127 },
  { supplier: "Teknorot", country: "Turkey", country_code: "TR", city: "Istanbul", parts: 2, available_units: 640, x: 581, y: 136 },
];

export const partsCatalog = initialProducts;

export const stockOverview = [
  {
    label: "Healthy Stock",
    value: 148,
    icon: ShieldCheck,
    status: "Healthy" as StockHealth,
    detail: "Stable reorder coverage",
  },
  {
    label: "Low Stock Items",
    value: 34,
    icon: AlertTriangle,
    status: "Low Stock" as StockHealth,
    detail: "Restock within 7 days",
  },
  {
    label: "Critical Items",
    value: 12,
    icon: Timer,
    status: "Critical" as StockHealth,
    detail: "Action required today",
  },
  {
    label: "Overstock Items",
    value: 27,
    icon: Boxes,
    status: "Overstock" as StockHealth,
    detail: "Reduce reorder volume",
  },
];

export const stockComparison = [
  { name: "Tires", current: 42, recommended: 90, status: "Low Stock" as StockHealth },
  { name: "Brakes", current: 84, recommended: 72, status: "Healthy" as StockHealth },
  { name: "Filters", current: 210, recommended: 125, status: "Overstock" as StockHealth },
  { name: "Engine", current: 25, recommended: 85, status: "Critical" as StockHealth },
  { name: "Accessories", current: 96, recommended: 90, status: "Healthy" as StockHealth },
];

export const categoryHealth = [
  { category: "Tires", status: "Low Stock" as StockHealth, coverage: "47%" },
  { category: "Brakes", status: "Healthy" as StockHealth, coverage: "117%" },
  { category: "Filters", status: "Overstock" as StockHealth, coverage: "168%" },
  { category: "Engine Parts", status: "Critical" as StockHealth, coverage: "29%" },
  { category: "Accessories", status: "Healthy" as StockHealth, coverage: "107%" },
];

export const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];

export const categorySalesSeries: SalesSeries[] = [
  { category: "Tires", color: "#fb923c", values: [32, 36, 42, 49, 62, 78] },
  { category: "Brakes", color: "#facc15", values: [48, 46, 51, 55, 58, 61] },
  { category: "Filters", color: "#94a3b8", values: [64, 66, 65, 70, 69, 71] },
  { category: "Engine Parts", color: "#f87171", values: [26, 31, 36, 43, 44, 52] },
  { category: "Accessories", color: "#38bdf8", values: [18, 24, 29, 41, 53, 68] },
  { category: "Batteries", color: "#a7f3d0", values: [28, 30, 35, 37, 44, 50] },
];

export const marketTrends: MarketTrend[] = [
  {
    id: "trend-accessories",
    title: "Exterior accessories are accelerating",
    detail: "Customers are increasingly searching for car stickers, trims, and personalization packs.",
    priority: "High",
    category: "Accessories",
  },
  {
    id: "trend-tires",
    title: "Winter tire interest is rising",
    detail: "Search and quote activity is climbing ahead of colder weather and fleet seasonal changes.",
    priority: "High",
    category: "Tires",
  },
  {
    id: "trend-wipers",
    title: "Rain forecasts are lifting wiper demand",
    detail: "Wiper blade demand increased after heavy rain forecasts in the region.",
    priority: "Medium",
    category: "Accessories",
  },
  {
    id: "trend-battery",
    title: "Battery replacement searches are up",
    detail: "Battery queries are trending above baseline this month, especially for older Peugeot models.",
    priority: "Medium",
    category: "Batteries",
  },
  {
    id: "trend-filters",
    title: "Oil filter sales remain steady",
    detail: "Oil filter movement is stable across Peugeot 2008 and 3008 service cycles.",
    priority: "Stable",
    category: "Filters",
  },
];

export const initialClientOrders: ClientOrder[] = [
  {
    id: "CL-4821",
    client: "Andrei Popescu",
    items: [{ productId: "brake-pads-208", name: "Brake Pads Peugeot 208", sku: "PEU-208-BRK", quantity: 3, unitPrice: 48 }],
    requestedTime: "14:30",
    status: "Pending",
    createdAt: nowIso(),
  },
  {
    id: "CL-4822",
    client: "Mara Service Auto",
    items: [{ productId: "wiper-blades-universal", name: "Wiper Blades Universal", sku: "WIP-UNI-22", quantity: 8, unitPrice: 22 }],
    requestedTime: "16:00",
    status: "Pending",
    createdAt: nowIso(),
  },
  {
    id: "CL-4815",
    client: "Ionescu Fleet",
    items: [{ productId: "oil-filter-2008", name: "Oil Filter Peugeot 2008", sku: "PEU-2008-OIL", quantity: 12, unitPrice: 18 }],
    requestedTime: "11:45",
    status: "Approved",
    createdAt: nowIso(),
    stockApplied: true,
  },
];

export const initialSupplierOrders: SupplierOrder[] = [
  {
    id: "SO-1048",
    supplier: "Michelin",
    items: [{ productId: "winter-tires-205", name: "Winter Tires 205/55 R16", sku: "TYR-WIN-205", quantity: 35, unitPrice: 92 }],
    status: "Delivered",
    createdAt: nowIso(),
    estimatedArrival: "Arrived today",
  },
  {
    id: "SO-1049",
    supplier: "Bosch",
    items: [{ productId: "brake-pads-208", name: "Brake Pads Peugeot 208", sku: "PEU-208-BRK", quantity: 50, unitPrice: 48 }],
    status: "Approved",
    createdAt: nowIso(),
    estimatedArrival: "3 days",
  },
  {
    id: "SO-1050",
    supplier: "Valeo",
    items: [{ productId: "oil-filter-2008", name: "Oil Filter Peugeot 2008", sku: "PEU-2008-OIL", quantity: 80, unitPrice: 18 }],
    status: "Delayed",
    createdAt: nowIso(),
    estimatedArrival: "9 days",
  },
];

export const orderKpis = [
  {
    label: "Pending Orders",
    value: "18",
    detail: "Awaiting manager review",
    icon: Timer,
    tone: "orange",
  },
  {
    label: "Approved Orders",
    value: "24",
    detail: "Confirmed with suppliers",
    icon: BadgeCheck,
    tone: "green",
  },
  {
    label: "Supplier Delays",
    value: "4",
    detail: "Average delay 3.5 days",
    icon: AlertTriangle,
    tone: "red",
  },
  {
    label: "Estimated Order Value",
    value: "EUR 42.8K",
    detail: "Open purchase pipeline",
    icon: Gauge,
    tone: "steel",
  },
] as const;

export const orders = initialSupplierOrders.map((order) => ({
  id: order.id,
  supplier: order.supplier,
  parts: order.items.map((item) => item.name).join(", "),
  quantity: order.items.reduce((sum, item) => sum + item.quantity, 0),
  status: order.status,
  arrival: order.estimatedArrival,
}));
