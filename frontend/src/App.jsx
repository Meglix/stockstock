import { useEffect, useMemo, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import { ComposableMap, Geographies, Geography, Marker, ZoomableGroup } from "react-simple-maps";
import AuthPage from "./AuthPage";
import worldGeoUrl from "world-atlas/countries-110m.json?url";

const SLICE_GRADIENTS = [
  ["#7dd3fc", "#0ea5e9"],
  ["#38bdf8", "#0284c7"],
  ["#bae6fd", "#0369a1"],
  ["#93c5fd", "#1d4ed8"],
  ["#60a5fa", "#2563eb"],
  ["#a5f3fc", "#0891b2"],
  ["#e0f2fe", "#0c4a6e"],
  ["#cffafe", "#164e63"],
];

const CONTINENT_COLORS = {
  Africa: "#c7d2fe",
  Antarctica: "#e2e8f0",
  Asia: "#bfdbfe",
  Europe: "#99f6e4",
  "North America": "#a5b4fc",
  Oceania: "#bae6fd",
  "South America": "#ddd6fe",
};

const COUNTRY_LON_LAT = {
  AT: [14.55, 47.52],
  BE: [4.47, 50.50],
  BG: [25.49, 42.73],
  CH: [8.23, 46.82],
  CZ: [15.47, 49.82],
  DE: [10.45, 51.16],
  DK: [9.50, 56.26],
  EE: [25.01, 58.60],
  ES: [-3.75, 40.46],
  FI: [25.75, 61.92],
  FR: [2.21, 46.22],
  GB: [-3.43, 55.38],
  GR: [21.82, 39.07],
  HR: [15.20, 45.10],
  HU: [19.50, 47.16],
  IE: [-8.24, 53.41],
  IT: [12.57, 41.87],
  LT: [23.88, 55.17],
  LU: [6.13, 49.82],
  LV: [24.60, 56.88],
  NL: [5.29, 52.13],
  NO: [8.47, 60.47],
  PL: [19.15, 51.92],
  PT: [-8.22, 39.40],
  RO: [24.97, 45.94],
  SE: [18.64, 60.13],
  SI: [14.99, 46.15],
  SK: [19.70, 48.67],
};

const USER_NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", subtitle: "Your location inventory snapshot" },
  { key: "parts", label: "Parts", subtitle: "Parts catalog in your scope" },
  { key: "stock", label: "Stock", subtitle: "Stock visibility for assigned locations" },
  { key: "orders", label: "Orders", subtitle: "Placed orders and delivery status" },
];

const ADMIN_NAV_ITEMS = [
  { key: "dashboard", label: "Admin Dashboard", subtitle: "Global inventory and performance" },
  { key: "inventory", label: "Inventory", subtitle: "Parts and stock management" },
  { key: "suppliers", label: "Suppliers", subtitle: "Supplier portfolio and metrics" },
  { key: "orders", label: "Orders", subtitle: "All order workflows and control" },
  { key: "analytics", label: "Analytics", subtitle: "KPIs, forecasts, recommendations" },
];

function DashboardIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: 15, height: 15 }}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

function PartsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
      <path d="m3.3 7 8.7 5 8.7-5" />
      <path d="M12 22V12" />
    </svg>
  );
}

function StockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="6" rx="1" />
      <rect x="3" y="14" width="18" height="6" rx="1" />
      <line x1="8" y1="7" x2="8.01" y2="7" />
      <line x1="8" y1="17" x2="8.01" y2="17" />
    </svg>
  );
}

function OrdersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 18h6" />
      <path d="M10 22h4" />
      <path d="M12 2v8" />
      <path d="m8 6 4-4 4 4" />
      <rect x="4" y="10" width="16" height="10" rx="2" />
    </svg>
  );
}

function InventoryIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h10" />
      <circle cx="18" cy="18" r="2" />
    </svg>
  );
}

function SuppliersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 21h18" />
      <path d="M5 21V8l7-4 7 4v13" />
      <path d="M9 21v-6h6v6" />
      <path d="M9 10h.01" />
      <path d="M15 10h.01" />
    </svg>
  );
}

function AnalyticsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 3v18h18" />
      <path d="m7 15 4-4 3 3 5-6" />
      <path d="m17 8h2v2" />
    </svg>
  );
}

function iconForPage(pageKey) {
  if (pageKey === "dashboard") return <DashboardIcon />;
  if (pageKey === "parts") return <PartsIcon />;
  if (pageKey === "stock") return <StockIcon />;
  if (pageKey === "orders") return <OrdersIcon />;
  if (pageKey === "inventory") return <InventoryIcon />;
  if (pageKey === "suppliers") return <SuppliersIcon />;
  if (pageKey === "analytics") return <AnalyticsIcon />;
  return <DashboardIcon />;
}

function PagePlaceholder({ title, text }) {
  return (
    <div className="card">
      <div className="state">
        <strong>{title}</strong>
        <p style={{ margin: "6px 0 0", color: "#475569" }}>{text}</p>
      </div>
    </div>
  );
}

function SupplierWorldMap({ suppliers, selectedSupplierId, onSelectSupplier }) {
  const [mapZoom, setMapZoom] = useState(1.9);
  const [mapCenter, setMapCenter] = useState([14, 50]);

  const suppliersByCountry = useMemo(() => {
    const grouped = new Map();
    suppliers.forEach((supplier) => {
      const code = (supplier.country_code || "").toUpperCase();
      if (!grouped.has(code)) {
        grouped.set(code, []);
      }
      grouped.get(code).push(supplier);
    });
    return grouped;
  }, [suppliers]);

  return (
    <div className="map-card">
      <div className="map-card__head">
        <div className="map-card__meta">
          <h3>Supplier World Map</h3>
        </div>
        <div className="map-hint map-hint--inline">Tip: drag to pan, use mouse wheel to zoom.</div>
      </div>

      <div className="gadget-body">
        <div className="world-map world-map--real" role="img" aria-label="World map with supplier locations">
        <ComposableMap
          projection="geoNaturalEarth1"
          projectionConfig={{ scale: 145 }}
          width={800}
          height={380}
          style={{ width: "100%", height: "100%" }}
        >
          <ZoomableGroup
            zoom={mapZoom}
            center={mapCenter}
            onMoveEnd={(position) => {
              setMapZoom(position.zoom);
              setMapCenter(position.coordinates);
            }}
            maxZoom={6}
          >
            <Geographies geography={worldGeoUrl}>
              {({ geographies }) => {
              const markers = [];
              const unmapped = [];
              suppliersByCountry.forEach((countrySuppliers, code) => {
                const base = COUNTRY_LON_LAT[code];
                if (!base) {
                  unmapped.push(...countrySuppliers);
                  return;
                }

                countrySuppliers.forEach((supplier, idx) => {
                  const count = countrySuppliers.length;
                  const angle = (Math.PI * 2 * idx) / Math.max(count, 1);
                  const radius = count === 1 ? 0 : 1.2 + Math.floor(idx / 6) * 0.7;
                  const lon = base[0] + Math.cos(angle) * radius;
                  const lat = base[1] + Math.sin(angle) * radius;
                  markers.push({
                    id: supplier.id,
                    supplierId: String(supplier.id),
                    name: supplier.supplier_name,
                    code,
                    coordinates: [lon, lat],
                  });
                });
              });

                return (
                  <>
                    {geographies.map((geo) => {
                      const continent = geo.properties.CONTINENT || "";
                      const fill = CONTINENT_COLORS[continent] || "#dbeafe";
                      return (
                        <Geography
                          key={geo.rsmKey}
                          geography={geo}
                          className="world-map__country"
                          style={{
                            default: { fill, outline: "none" },
                            hover: { fill: "#93c5fd", outline: "none" },
                            pressed: { fill: "#7dd3fc", outline: "none" },
                          }}
                        />
                      );
                    })}

                    {markers.map((marker) => (
                      <Marker key={marker.id} coordinates={marker.coordinates}>
                        <g
                          className={`world-map__pin-group ${selectedSupplierId === marker.supplierId ? "world-map__pin-group--selected" : ""} ${selectedSupplierId && selectedSupplierId !== marker.supplierId ? "world-map__pin-group--dim" : ""}`}
                          onClick={() => onSelectSupplier(marker.supplierId)}
                        >
                          <circle className="world-map__pin-core" r="3.2" />
                          <circle className="world-map__pin-ring" r="5.6" />
                          <text className="world-map__pin-label" y="-10">
                            {marker.code}
                          </text>
                          <title>{`${marker.name} (${marker.code})`}</title>
                        </g>
                      </Marker>
                    ))}

                    {unmapped.length > 0 && (
                      <text x="20" y="360" className="world-map__note">
                        Unmapped suppliers: {unmapped.map((s) => s.supplier_name).join(", ")}
                      </text>
                    )}
                  </>
                );
              }}
            </Geographies>
          </ZoomableGroup>
        </ComposableMap>
        </div>
      </div>
    </div>
  );
}

function SupplierPartsChart({ parts, suppliers, selectedSupplierId, onSelectSupplier }) {
  const data = useMemo(() => {
    const counts = new Map();
    parts.forEach((part) => {
      const key = part.supplier_id ? String(part.supplier_id) : "UNKNOWN";
      counts.set(key, (counts.get(key) || 0) + 1);
    });

    return suppliers
      .map((supplier) => ({
        supplierId: String(supplier.id),
        supplier: supplier.supplier_name,
        parts: counts.get(String(supplier.id)) || 0,
      }))
      .filter((item) => item.parts > 0)
      .sort((a, b) => b.parts - a.parts)
      .slice(0, 8);
  }, [parts, suppliers]);

  return (
    <div className="card gadget-card">
      <div className="gadget-head">
        <h3>Parts by Supplier</h3>
        <p>Top suppliers by number of parts in catalog.</p>
      </div>

      <div className="gadget-body">
        {data.length === 0 ? (
          <div className="state">No supplier-part data available.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 40 }}>
              <defs>
                <linearGradient id="supplierBarGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" />
                  <stop offset="100%" stopColor="#0284c7" />
                </linearGradient>
                <linearGradient id="supplierBarGradientActive" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0ea5e9" />
                  <stop offset="100%" stopColor="#0369a1" />
                </linearGradient>
                <linearGradient id="supplierBarGradientDim" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#dbeafe" />
                  <stop offset="100%" stopColor="#93c5fd" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#dbeafe" />
              <XAxis
                dataKey="supplierId"
                tick={{ fontSize: 11, fill: "#334155" }}
                angle={-22}
                textAnchor="end"
                interval={0}
                height={50}
              />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#334155" }} />
              <Tooltip
                formatter={(value, _name, context) => [value, context?.payload?.supplier || "Supplier"]}
                labelFormatter={(label) => `Supplier ID: ${label}`}
                cursor={{ fill: "rgba(14, 165, 233, 0.08)" }}
                contentStyle={{ borderRadius: 10, border: "1px solid #bfdbfe", background: "rgba(255, 255, 255, 0.95)", color: "#0f172a" }}
              />
              <Bar
                dataKey="parts"
                radius={[6, 6, 0, 0]}
                activeBar={{ fill: "url(#supplierBarGradientActive)" }}
                onClick={(entry) => {
                  if (entry?.supplierId) {
                    onSelectSupplier(entry.supplierId);
                  }
                }}
              >
                {data.map((entry) => (
                  <Cell
                    key={entry.supplierId}
                    fill={selectedSupplierId ? (selectedSupplierId === entry.supplierId ? "url(#supplierBarGradientActive)" : "url(#supplierBarGradientDim)") : "url(#supplierBarGradient)"}
                    cursor="pointer"
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

function DashboardOverview({ loading, error, parts, chartData }) {
  if (loading) {
    return <div className="state">Loading parts...</div>;
  }

  if (error) {
    return <div className="state state--error">{error}</div>;
  }

  return (
    <div className="card">
      <div className="stats">
        <div>
          <span>Total Available Parts</span>
          <strong>{parts.length}</strong>
        </div>
        <div>
          <span>Categories</span>
          <strong>{chartData.length}</strong>
        </div>
      </div>

      <div className="chart-layout">
        <div className="chart-panel">
          {chartData.length === 0 ? (
            <div className="state">No parts data available.</div>
          ) : (
            <ResponsiveContainer width="100%" height={360}>
              <PieChart>
                <defs>
                  {chartData.map((entry, idx) => {
                    const [start, end] = SLICE_GRADIENTS[idx % SLICE_GRADIENTS.length];
                    return (
                      <linearGradient id={`sliceGradient-${entry.name}-${idx}`} x1="0" y1="0" x2="1" y2="1" key={`gradient-${entry.name}-${idx}`}>
                        <stop offset="0%" stopColor={start} />
                        <stop offset="100%" stopColor={end} />
                      </linearGradient>
                    );
                  })}
                </defs>

                <Pie data={chartData} dataKey="value" nameKey="name" outerRadius={130} innerRadius={62} paddingAngle={2} stroke="none">
                  {chartData.map((entry, idx) => (
                    <Cell key={entry.name} fill={`url(#sliceGradient-${entry.name}-${idx})`} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #bfdbfe", boxShadow: "0 10px 25px rgba(15, 23, 42, 0.12)" }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="legend">
          {chartData.map((item, idx) => (
            <div className="legend__item" key={item.name}>
              <span
                className="dot"
                style={{
                  backgroundImage: `linear-gradient(135deg, ${SLICE_GRADIENTS[idx % SLICE_GRADIENTS.length][0]}, ${SLICE_GRADIENTS[idx % SLICE_GRADIENTS.length][1]})`,
                }}
              />
              <span>{item.name}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function UserPageContent({ activePage, loading, error, parts, chartData, user, suppliers }) {
  const [selectedSupplierId, setSelectedSupplierId] = useState(null);

  function handleSelectSupplier(supplierId) {
    const normalized = supplierId ? String(supplierId) : null;
    setSelectedSupplierId((current) => (current === normalized ? null : normalized));
  }

  if (activePage === "dashboard") {
    return (
      <>
        <DashboardOverview
          loading={loading}
          error={error}
          parts={parts}
          chartData={chartData}
        />

        <div className="dashboard-gadgets">
          <SupplierPartsChart
            parts={parts}
            suppliers={suppliers}
            selectedSupplierId={selectedSupplierId}
            onSelectSupplier={handleSelectSupplier}
          />
          <div className="card card--map-gadget">
            <SupplierWorldMap
              suppliers={suppliers}
              selectedSupplierId={selectedSupplierId}
              onSelectSupplier={handleSelectSupplier}
            />
          </div>
        </div>
      </>
    );
  }

  if (activePage === "parts") {
    return (
      <PagePlaceholder
        title="Parts"
        text="This page will display parts available to the user within assigned locations."
      />
    );
  }

  if (activePage === "stock") {
    return (
      <PagePlaceholder
        title="Stock"
        text="This page will display stock for the user's assigned locations only."
      />
    );
  }

  return (
    <PagePlaceholder
      title="Orders"
      text="This page will show order lifecycle for orders created by the user."
    />
  );
}

function AdminPageContent({ activePage, loading, error, parts, chartData, user, suppliers }) {
  if (activePage === "dashboard") {
    return <DashboardOverview loading={loading} error={error} parts={parts} chartData={chartData} />;
  }

  if (activePage === "inventory") {
    return (
      <PagePlaceholder
        title="Inventory"
        text="This page will centralize parts and stock management across all locations."
      />
    );
  }

  if (activePage === "suppliers") {
    return (
      <PagePlaceholder
        title="Suppliers"
        text="This page will include supplier admin operations and performance overview."
      />
    );
  }

  if (activePage === "orders") {
    return (
      <PagePlaceholder
        title="Orders"
        text="This page will show all order flows with admin-level controls."
      />
    );
  }

  return (
    <PagePlaceholder
      title="Analytics"
      text="This page will aggregate KPIs, forecasts, and recommendations at global level."
    />
  );
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("auth_token") || "");
  const [user, setUser] = useState(() => {
    const cached = localStorage.getItem("auth_user");
    return cached ? JSON.parse(cached) : null;
  });
  const [authError, setAuthError] = useState("");

  const [parts, setParts] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerCollapsed, setDrawerCollapsed] = useState(false);
  const [logoutConfirm, setLogoutConfirm] = useState(false);
  const [activePage, setActivePage] = useState("dashboard");

  const navItems = user?.role === "admin" ? ADMIN_NAV_ITEMS : USER_NAV_ITEMS;

  const activeNavItem = useMemo(() => {
    return navItems.find((item) => item.key === activePage) || navItems[0];
  }, [activePage, navItems]);

  const chartData = useMemo(() => {
    const byCategory = {};
    for (const p of parts) {
      const category = p.category || "Uncategorized";
      byCategory[category] = (byCategory[category] || 0) + 1;
    }
    return Object.entries(byCategory)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [parts]);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }

    async function loadDashboard() {
      setLoading(true);
      setError("");
      try {
        const [healthRes, partsRes, suppliersRes] = await Promise.all([
          fetch("/api/health", { headers: { Authorization: `Bearer ${token}` } }),
          fetch("/api/parts", { headers: { Authorization: `Bearer ${token}` } }),
          fetch("/api/suppliers-info", { headers: { Authorization: `Bearer ${token}` } }),
        ]);

        if (!healthRes.ok || !partsRes.ok) {
          throw new Error("Could not load dashboard data.");
        }

        setHealth(await healthRes.json());
        const partsData = await partsRes.json();
        setParts(Array.isArray(partsData) ? partsData : []);

        if (suppliersRes.ok) {
          const suppliersData = await suppliersRes.json();
          setSuppliers(Array.isArray(suppliersData) ? suppliersData : []);
        } else {
          setSuppliers([]);
        }
      } catch (err) {
        setError(err?.message || "Unexpected error while loading data.");
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, [token]);

  useEffect(() => {
    if (!user?.role) {
      return;
    }
    setActivePage("dashboard");
  }, [user?.role]);

  function handleAuthSuccess(data) {
    if (!data?.access_token || !data?.user) return;
    localStorage.setItem("auth_token", data.access_token);
    localStorage.setItem("auth_user", JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
    setAuthError("");
  }

  function logout() {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_user");
    setToken("");
    setUser(null);
    setParts([]);
    setSuppliers([]);
    setHealth(null);
    setError("");
    setDrawerOpen(false);
    setDrawerCollapsed(false);
    setLogoutConfirm(false);
  }

  if (!token || !user) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} initialError={authError} />;
  }

  return (
    <div className="shell">
      <aside className={`sidebar ${drawerOpen ? "sidebar--open" : ""} ${drawerCollapsed ? "sidebar--collapsed" : ""}`}>
        <div className="sidebar__header">
          <div className="sidebar__brand" aria-label="Stock Optimizer">
            <span className="sidebar__brand-full">Stock</span>
            <span className="sidebar__brand-full">Optimizer</span>
          </div>
          <button
            className="sidebar__collapse-btn"
            type="button"
            onClick={() => setDrawerCollapsed((v) => !v)}
            aria-label={drawerCollapsed ? "Show navigation drawer" : "Hide navigation drawer"}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 18, height: 18 }}>
              {drawerCollapsed
                ? <polyline points="9 18 15 12 9 6" />
                : <polyline points="15 18 9 12 15 6" />}
            </svg>
          </button>
        </div>
        <nav className="sidebar__nav">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={`sidebar__item ${activePage === item.key ? "sidebar__item--active" : ""}`}
              type="button"
              onClick={() => {
                setActivePage(item.key);
                setDrawerOpen(false);
              }}
            >
              <span className="sidebar__icon">{iconForPage(item.key)}</span>
              <span className="sidebar__text">{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar__footer">
          <button className="sidebar__item sidebar__logout" type="button" onClick={() => setLogoutConfirm(true)}>
            <span className="sidebar__icon"><LogoutIcon /></span>
            <span className="sidebar__text">Logout</span>
          </button>
        </div>
      </aside>

      {drawerOpen && <button className="drawer-overlay" onClick={() => setDrawerOpen(false)} aria-label="Close menu" />}

      <main className="main-area">
        <header className="topbar">
          <button className="menu-btn" onClick={() => setDrawerOpen((v) => !v)} aria-label="Open menu">☰</button>
          <div className="topbar__title-wrap">
            <h1>{activeNavItem?.label || "Dashboard"}</h1>
            <p>{activeNavItem?.subtitle || "Role-based workspace"}</p>
          </div>
          <div className="topbar__right">
            <span className="user-pill">{user?.username} ({user?.role})</span>
            <span className={`health-pill ${health?.status === "ok" ? "health-pill--ok" : "health-pill--fail"}`}>
              {health?.status === "ok" ? "API Online" : "API Error"}
            </span>
            <button className="btn-ghost btn-logout" onClick={() => setLogoutConfirm(true)}>
                <LogoutIcon />
                Logout
              </button>
          </div>
        </header>

        <section className="content">
          {user?.role === "admin" ? (
            <AdminPageContent
              activePage={activePage}
              loading={loading}
              error={error}
              parts={parts}
              chartData={chartData}
              user={user}
              suppliers={suppliers}
            />
          ) : (
            <UserPageContent
              activePage={activePage}
              loading={loading}
              error={error}
              parts={parts}
              chartData={chartData}
              user={user}
              suppliers={suppliers}
            />
          )}
        </section>
      </main>

      {logoutConfirm && (
        <div className="modal-overlay" onClick={() => setLogoutConfirm(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-icon">
              <LogoutIcon />
            </div>
            <h2 className="modal-title">Sign out?</h2>
            <p className="modal-subtitle">You will need to log in again to continue.</p>
            <div className="modal-actions">
              <button className="modal-btn modal-btn--cancel" onClick={() => setLogoutConfirm(false)}>Cancel</button>
              <button className="modal-btn modal-btn--confirm" onClick={logout}>Yes, sign out</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
