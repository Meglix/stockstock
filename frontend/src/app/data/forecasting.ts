export type ForecastHorizon = 7 | 14 | 21;

export type ForecastPoint = {
  label: string;
  actual?: number;
  forecast: number;
  confidenceLow: number;
  confidenceHigh: number;
};

export type ForecastLocation = {
  id: string;
  city: string;
  climate: string;
};

export type ForecastPart = {
  sku: string;
  name: string;
  category: string;
};

export type ForecastQuery = {
  locationId: string;
  category: string;
  sku: string;
  horizon: ForecastHorizon;
};

export type BackendForecastRow = {
  forecast_date?: string;
  horizon_day?: number | string;
  sku?: string;
  part_name?: string;
  category?: string;
  location_id?: string;
  city?: string;
  predicted_quantity?: number | string;
  predicted_revenue_eur?: number | string;
  prediction_scope?: string;
  weather_source?: string;
};

export type BackendForecastResponse = {
  available?: boolean;
  source?: string;
  location_id?: string | null;
  requested_horizon?: number;
  source_horizon?: number;
  items?: BackendForecastRow[];
  error?: string | null;
};

export type BackendForecastResult = {
  points: ForecastPoint[];
  response: BackendForecastResponse;
};

export const forecastHorizons: ForecastHorizon[] = [7, 14, 21];
export const mlForecastBaseUrl = process.env.NEXT_PUBLIC_ML_FORECAST_URL?.replace(/\/$/, "") ?? "";

export const forecastLocations: ForecastLocation[] = [
  { id: "FI_HEL", city: "Helsinki", climate: "Nordic" },
  { id: "SE_STO", city: "Stockholm", climate: "Nordic" },
  { id: "EE_TLL", city: "Tallinn", climate: "Baltic" },
  { id: "DK_CPH", city: "Copenhagen", climate: "Coastal" },
  { id: "NL_AMS", city: "Amsterdam", climate: "Maritime" },
  { id: "DE_BER", city: "Berlin", climate: "Continental" },
  { id: "PL_WAW", city: "Warsaw", climate: "Continental" },
  { id: "CZ_PRG", city: "Prague", climate: "Continental" },
  { id: "RO_BUC", city: "Bucharest", climate: "Continental" },
  { id: "IT_MIL", city: "Milan", climate: "Southern continental" },
  { id: "ES_MAD", city: "Madrid", climate: "Dry continental" },
  { id: "FR_PAR", city: "Paris", climate: "Temperate" },
];

export const forecastParts: ForecastPart[] = [
  { sku: "PEU-WF-WINTER-5L", name: "Winter washer fluid -20C 5L", category: "Winter Fluids" },
  { sku: "PEU-WIPER-650", name: "Front wiper blades 650mm", category: "Wipers" },
  { sku: "PEU-BATT-70AH", name: "Battery 70Ah AGM/EFB", category: "Battery" },
  { sku: "PEU-AC-REFILL", name: "AC refill kit R134a/R1234yf", category: "AC Cooling" },
  { sku: "PEU-CABIN-CARBON", name: "Cabin carbon filter", category: "Filters" },
  { sku: "PEU-SUMMER-TIRE-205", name: "Summer tire 205/55 R16", category: "Tires" },
  { sku: "PEU-WINTER-TIRE-205", name: "Winter tire 205/55 R16", category: "Tires" },
  { sku: "PEU-ANTIFREEZE-G12", name: "Antifreeze G12 concentrate 1L", category: "Coolant" },
  { sku: "PEU-COOLANT-PREMIX", name: "Coolant premix 5L", category: "Coolant" },
  { sku: "PEU-OIL-5W30-5L", name: "Engine oil 5W30 5L", category: "Maintenance" },
  { sku: "PEU-OIL-FILTER", name: "Oil filter", category: "Maintenance" },
  { sku: "PEU-AIR-FILTER", name: "Engine air filter", category: "Filters" },
  { sku: "PEU-BRAKE-PADS-F", name: "Front brake pads", category: "Brakes" },
  { sku: "PEU-HEADLIGHT-H7", name: "Headlight bulb H7", category: "Lighting" },
  { sku: "PEU-RUBBER-MATS", name: "Peugeot rubber mats", category: "Accessories" },
  { sku: "PEU-ADBLUE-10L", name: "AdBlue 10L", category: "Consumables" },
  { sku: "PEU-BRAKE-FLUID-DOT4", name: "Brake fluid DOT4 1L", category: "Brakes" },
  { sku: "PEU-SPARK-PLUG", name: "Gasoline spark plug", category: "Maintenance" },
];

const locationMultiplier: Record<string, number> = {
  FI_HEL: 1.16,
  SE_STO: 1.13,
  EE_TLL: 1.08,
  DK_CPH: 1.05,
  NL_AMS: 1.02,
  DE_BER: 1.04,
  PL_WAW: 1,
  CZ_PRG: 0.98,
  RO_BUC: 1.18,
  IT_MIL: 0.96,
  ES_MAD: 1.03,
  FR_PAR: 1.01,
};

const categoryBase: Record<string, number> = {
  Tires: 34,
  "Winter Fluids": 42,
  Wipers: 18,
  Battery: 26,
  "AC Cooling": 24,
  Filters: 28,
  Brakes: 31,
  Coolant: 22,
  Maintenance: 23,
  Lighting: 16,
  Accessories: 14,
  Consumables: 18,
};

function hashText(value: string) {
  return value.split("").reduce((sum, char, index) => sum + char.charCodeAt(0) * (index + 3), 0);
}

function clampDemand(value: number) {
  return Math.max(2, Math.round(value));
}

export function getForecastCategories(parts = forecastParts) {
  return Array.from(new Set(parts.map((part) => part.category)));
}

export function hasConfiguredMlForecastSource() {
  return true;
}

export function getForecastSeries(query: ForecastQuery): ForecastPoint[] {
  const part = forecastParts.find((item) => item.sku === query.sku);
  const category = part?.category || query.category;
  const seed = hashText(`${query.locationId}-${query.sku}-${query.category}`);
  const base = (categoryBase[category] ?? 26) * (locationMultiplier[query.locationId] ?? 1);
  const points: ForecastPoint[] = [];
  const historyLength = 7;
  const totalPoints = historyLength + query.horizon;

  for (let index = 0; index < totalPoints; index += 1) {
    const forecastDay = index - historyLength + 1;
    const isHistory = forecastDay <= 0;
    const trend = forecastDay > 0 ? forecastDay * (category === "Tires" || category === "Winter Fluids" ? 1.25 : 0.42) : forecastDay * 0.36;
    const weeklyWave = Math.sin((index + seed) * 0.85) * 4.2;
    const localPulse = ((seed + index * 7) % 9) - 4;
    const forecast = clampDemand(base + trend + weeklyWave + localPulse);
    const actual = isHistory ? clampDemand(forecast + Math.cos((index + seed) * 0.7) * 3 - 1) : undefined;
    const confidence = Math.max(4, Math.round(forecast * (0.1 + Math.max(0, forecastDay) * 0.004)));

    points.push({
      label: isHistory ? `D${forecastDay}` : `D+${forecastDay}`,
      actual,
      forecast,
      confidenceLow: clampDemand(forecast - confidence),
      confidenceHigh: clampDemand(forecast + confidence),
    });
  }

  return points;
}

export function buildForecastInsight(query: ForecastQuery, points: ForecastPoint[]) {
  const part = forecastParts.find((item) => item.sku === query.sku);
  const location = forecastLocations.find((item) => item.id === query.locationId);
  const forecastWindow = points.slice(-query.horizon);
  const totalDemand = forecastWindow.reduce((sum, point) => sum + point.forecast, 0);
  const firstHalf = forecastWindow.slice(0, Math.ceil(forecastWindow.length / 2)).reduce((sum, point) => sum + point.forecast, 0);
  const secondHalf = forecastWindow.slice(Math.ceil(forecastWindow.length / 2)).reduce((sum, point) => sum + point.forecast, 0);
  const direction = secondHalf >= firstHalf ? "increase" : "soften";
  const action =
    direction === "increase"
      ? "checking stock levels and preparing a supplier order if inventory is below the recommended threshold"
      : "monitoring open client orders before increasing supplier quantities";

  return `Based on recent demand signals in ${location?.city ?? "the selected store"}, ${part?.name ?? query.category} demand is expected to ${direction} over the next ${query.horizon} days. Forecast demand is around ${Math.round(totalDemand).toLocaleString()} units, so the system recommends ${action}.`;
}

function authHeaders() {
  const headers = new Headers();
  if (typeof window === "undefined") return headers;

  const token = window.localStorage.getItem("auth_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

function numericValue(value: unknown, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeBackendForecastRows(rows: BackendForecastRow[], query: ForecastQuery): ForecastPoint[] {
  return rows
    .filter((row) => !row.sku || row.sku.toUpperCase() === query.sku.toUpperCase())
    .filter((row) => !row.location_id || row.location_id.toUpperCase() === query.locationId.toUpperCase())
    .map((row, index) => {
      const horizonDay = numericValue(row.horizon_day, index + 1);
      const forecast = clampDemand(numericValue(row.predicted_quantity, 0));
      const confidence = Math.max(3, Math.round(forecast * 0.12));

      return {
        label: `D+${horizonDay}`,
        forecast,
        confidenceLow: clampDemand(forecast - confidence),
        confidenceHigh: clampDemand(forecast + confidence),
      };
    })
    .slice(0, query.horizon);
}

export function forecastSourceLabel(response?: BackendForecastResponse | null) {
  if (!response) return "Loading forecast";
  if (response.source === "ml-service") return "Backend ML service";
  if (response.source === "ml-csv-fallback") return "Generated ML CSV";
  if (response.source === "mock-fallback") return "Backend fallback";
  return "Backend forecast";
}

export async function fetchBackendForecastSeries(query: ForecastQuery, signal?: AbortSignal): Promise<BackendForecastResult> {
  const params = new URLSearchParams({
    sku: query.sku,
    location: query.locationId,
    horizon: String(query.horizon),
    limit: "240",
  });
  const response = await fetch(`/api/dashboard/ml/forecast?${params.toString()}`, {
    headers: authHeaders(),
    signal,
  });
  const data = (await response.json().catch(() => ({}))) as BackendForecastResponse;

  if (!response.ok) {
    throw new Error(typeof data.error === "string" ? data.error : `Forecast request failed (${response.status}).`);
  }

  return {
    points: normalizeBackendForecastRows(Array.isArray(data.items) ? data.items : [], query),
    response: data,
  };
}
