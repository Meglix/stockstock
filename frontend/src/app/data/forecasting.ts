export type ForecastHorizon = 7 | 14 | 21;

export type ForecastPoint = {
  label: string;
  date?: string;
  actual?: number;
  forecast?: number;
  confidenceLow?: number;
  confidenceHigh?: number;
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

export type BackendSalesHistoryRow = {
  date?: string;
  sku?: string;
  location_id?: string;
  quantity_sold?: number | string;
};

type BackendListResponse<T> = {
  available?: boolean;
  source?: string;
  items?: T[];
  error?: string | null;
};

type BackendWeatherRow = {
  date?: string;
  location_id?: string;
  city?: string;
  temperature_c?: number | string;
  rain_mm?: number | string;
  snow_cm?: number | string;
  cold_snap_flag?: number | string;
  heatwave_flag?: number | string;
  weather_spike_flag?: number | string;
  weather_source?: string;
  weather_provider?: string;
};

export type WeatherImpact = {
  sourceLabel: string;
  isMock: boolean;
  location: string;
  condition: string;
  temperature: number;
  impact: string;
  affectedCategories: string[];
  asOf?: string;
};

export type BackendForecastResult = {
  points: ForecastPoint[];
  response: BackendForecastResponse;
  warnings: string[];
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
  Batteries: 26,
  "AC Cooling": 24,
  "Air Conditioning": 24,
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

function roundDemand(value: number) {
  return Math.max(0, Math.round(value));
}

function numericValue(value: unknown): number | null {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function flagValue(value: unknown) {
  return Number(value) === 1 || value === true;
}

function validDate(value: unknown) {
  if (typeof value !== "string" || !value.trim()) return undefined;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? value.slice(0, 10) : undefined;
}

function formatShortDate(value: string | undefined) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en", { month: "short", day: "2-digit" }).format(date);
}

export function forecastCategoryLabel(category: string) {
  if (category === "Battery") return "Batteries";
  if (category === "AC Cooling") return "AC / Air Conditioning";
  return category;
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
  const today = new Date();

  for (let index = 0; index < historyLength; index += 1) {
    const dayOffset = index - historyLength + 1;
    const date = new Date(today);
    date.setDate(today.getDate() + dayOffset);
    const weeklyWave = Math.sin((index + seed) * 0.85) * 4.2;
    const localPulse = ((seed + index * 7) % 9) - 4;
    const baseline = roundDemand(base + dayOffset * 0.36 + weeklyWave + localPulse);
    const actual = roundDemand(baseline + Math.cos((index + seed) * 0.7) * 3 - 1);

    points.push({
      label: dayOffset === 0 ? "D0" : `D${dayOffset}`,
      date: date.toISOString().slice(0, 10),
      actual,
    });
  }

  for (let day = 1; day <= query.horizon; day += 1) {
    const date = new Date(today);
    date.setDate(today.getDate() + day);
    const trend = day * (category === "Tires" || category === "Winter Fluids" ? 1.25 : 0.42);
    const weeklyWave = Math.sin((historyLength + day + seed) * 0.85) * 4.2;
    const localPulse = ((seed + (historyLength + day) * 7) % 9) - 4;
    const forecast = roundDemand(base + trend + weeklyWave + localPulse);
    const confidence = Math.max(4, Math.round(forecast * (0.1 + day * 0.004)));

    points.push({
      label: `D+${day}`,
      date: date.toISOString().slice(0, 10),
      forecast,
      confidenceLow: roundDemand(forecast - confidence),
      confidenceHigh: roundDemand(forecast + confidence),
    });
  }

  return points;
}

export function buildForecastInsight(query: ForecastQuery, points: ForecastPoint[]) {
  const part = forecastParts.find((item) => item.sku === query.sku);
  const location = forecastLocations.find((item) => item.id === query.locationId);
  const forecastWindow = points.filter((point) => typeof point.forecast === "number").slice(0, query.horizon);
  if (forecastWindow.length < 2) {
    return `There is not enough normalized forecast data for ${part?.name ?? query.category} in ${location?.city ?? "the selected store"}. Use the fallback state instead of reading isolated points as a demand trend.`;
  }

  const totalDemand = forecastWindow.reduce((sum, point) => sum + (point.forecast ?? 0), 0);
  const firstHalf = forecastWindow.slice(0, Math.ceil(forecastWindow.length / 2)).reduce((sum, point) => sum + (point.forecast ?? 0), 0);
  const secondHalf = forecastWindow.slice(Math.ceil(forecastWindow.length / 2)).reduce((sum, point) => sum + (point.forecast ?? 0), 0);
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

function normalizeSalesHistoryRows(rows: BackendSalesHistoryRow[], query: ForecastQuery): ForecastPoint[] {
  const byDate = new Map<string, number>();

  rows.forEach((row) => {
    if (row.sku && row.sku.toUpperCase() !== query.sku.toUpperCase()) return;
    if (row.location_id && row.location_id.toUpperCase() !== query.locationId.toUpperCase()) return;
    const date = validDate(row.date);
    const quantity = numericValue(row.quantity_sold);
    if (!date || quantity === null || quantity < 0) return;
    byDate.set(date, (byDate.get(date) ?? 0) + quantity);
  });

  const sorted = Array.from(byDate.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .slice(-7);

  return sorted.map(([date, value], index) => {
    const offset = index - sorted.length + 1;
    return {
      label: offset === 0 ? "D0" : `D${offset}`,
      date,
      actual: roundDemand(value),
    };
  });
}

function normalizeBackendForecastRows(rows: BackendForecastRow[], query: ForecastQuery) {
  const warnings: string[] = [];
  const deduped = new Map<string, { date?: string; horizonDay: number; forecast: number }>();

  rows.forEach((row, index) => {
    if (row.sku && row.sku.toUpperCase() !== query.sku.toUpperCase()) return;
    if (row.location_id && row.location_id.toUpperCase() !== query.locationId.toUpperCase()) return;

    const forecast = numericValue(row.predicted_quantity);
    const horizonDay = Math.trunc(numericValue(row.horizon_day) ?? index + 1);
    const date = validDate(row.forecast_date);
    if (forecast === null || forecast < 0 || !Number.isFinite(horizonDay) || horizonDay < 1 || horizonDay > query.horizon) return;

    const key = date ?? `day-${horizonDay}`;
    deduped.set(key, { date, horizonDay, forecast });
  });

  const normalized = Array.from(deduped.values()).sort((left, right) => {
    if (left.date && right.date) return left.date.localeCompare(right.date);
    return left.horizonDay - right.horizonDay;
  });

  const availableDays = new Set(normalized.map((row) => row.horizonDay));
  const missingDays = forecastHorizons.includes(query.horizon)
    ? Array.from({ length: query.horizon }, (_, index) => index + 1).filter((day) => !availableDays.has(day))
    : [];

  if (missingDays.length > 0) {
    warnings.push(`Forecast is missing ${missingDays.length} day${missingDays.length === 1 ? "" : "s"} in the selected horizon; valid points are shown only.`);
  }

  if (normalized.length < 2) {
    warnings.push("Not enough valid forecast points to draw a connected forecast line.");
  }

  return {
    points: normalized.map((row) => {
      const forecast = roundDemand(row.forecast);
      const confidence = Math.max(3, Math.round(forecast * 0.12));
      return {
        label: `D+${row.horizonDay}`,
        date: row.date,
        forecast,
        confidenceLow: roundDemand(forecast - confidence),
        confidenceHigh: roundDemand(forecast + confidence),
      };
    }),
    warnings,
  };
}

export function forecastSourceLabel(response?: BackendForecastResponse | null) {
  if (!response) return "Loading forecast";
  if (response.source === "ml-service") return "Backend ML service";
  if (response.source === "ml-csv-fallback") return "Generated ML CSV";
  if (response.source === "mock-fallback") return "Backend fallback";
  return "Backend forecast";
}

export async function fetchBackendForecastSeries(query: ForecastQuery, signal?: AbortSignal): Promise<BackendForecastResult> {
  const forecastParams = new URLSearchParams({
    sku: query.sku,
    location: query.locationId,
    horizon: String(query.horizon),
    limit: "240",
  });
  const historyParams = new URLSearchParams({
    sku: query.sku,
    location: query.locationId,
    limit: "14",
  });

  const [forecastResponse, historyResponse] = await Promise.all([
    fetch(`/api/dashboard/ml/forecast?${forecastParams.toString()}`, {
      headers: authHeaders(),
      signal,
    }),
    fetch(`/api/ml/data/sales-history?${historyParams.toString()}`, {
      headers: authHeaders(),
      signal,
    }).catch(() => null),
  ]);

  const data = (await forecastResponse.json().catch(() => ({}))) as BackendForecastResponse;
  if (!forecastResponse.ok) {
    throw new Error(typeof data.error === "string" ? data.error : `Forecast request failed (${forecastResponse.status}).`);
  }

  const historyData = historyResponse && historyResponse.ok ? ((await historyResponse.json().catch(() => ({}))) as BackendListResponse<BackendSalesHistoryRow>) : null;
  const actualPoints = normalizeSalesHistoryRows(Array.isArray(historyData?.items) ? historyData.items : [], query);
  const normalizedForecast = normalizeBackendForecastRows(Array.isArray(data.items) ? data.items : [], query);

  return {
    points: normalizedForecast.points.length >= 2 ? [...actualPoints, ...normalizedForecast.points] : [],
    response: data,
    warnings: normalizedForecast.warnings,
  };
}

function demoWeatherImpact(query: ForecastQuery): WeatherImpact {
  const location = forecastLocations.find((item) => item.id === query.locationId);
  const coldCategories = ["Battery", "Winter Fluids", "Wipers", "Tires"];
  const heatCategories = ["AC Cooling", "Coolant"];
  const affectedCategories = query.locationId.startsWith("FI") || query.locationId.startsWith("DK") ? coldCategories : heatCategories;
  const cold = affectedCategories === coldCategories;

  return {
    sourceLabel: "Demo weather signal",
    isMock: true,
    location: location?.city ?? query.locationId,
    condition: cold ? "Cooler weather pressure" : "Warm weather pressure",
    temperature: cold ? 3 : 27,
    affectedCategories,
    impact: cold
      ? `${location?.city ?? "This location"} has a demo cold-weather signal. Battery, winter fluid, wiper and tire demand may increase.`
      : `${location?.city ?? "This location"} has a demo warm-weather signal. AC and coolant demand may increase.`,
  };
}

function normalizeWeatherImpact(rows: BackendWeatherRow[], query: ForecastQuery): WeatherImpact | null {
  const location = forecastLocations.find((item) => item.id === query.locationId);
  const sorted = rows
    .filter((row) => !row.location_id || row.location_id.toUpperCase() === query.locationId.toUpperCase())
    .filter((row) => validDate(row.date))
    .sort((left, right) => String(left.date).localeCompare(String(right.date)));

  if (!sorted.length) return null;

  const today = new Date().toISOString().slice(0, 10);
  const row = sorted.find((item) => String(item.date) >= today) ?? sorted[sorted.length - 1];
  const temperature = numericValue(row.temperature_c) ?? 0;
  const rain = numericValue(row.rain_mm) ?? 0;
  const snow = numericValue(row.snow_cm) ?? 0;
  const cold = flagValue(row.cold_snap_flag) || temperature <= 4 || snow > 0;
  const heat = flagValue(row.heatwave_flag) || temperature >= 25;
  const wet = rain >= 3 || flagValue(row.weather_spike_flag);

  if (cold) {
    return {
      sourceLabel: row.weather_source || row.weather_provider || "Cached Open-Meteo",
      isMock: false,
      location: row.city ?? location?.city ?? query.locationId,
      condition: snow > 0 ? "Snow/cold signal" : "Cold weather signal",
      temperature: Math.round(temperature),
      affectedCategories: ["Batteries", "Winter Fluids", "Wipers", "Tires"],
      asOf: validDate(row.date),
      impact: `Cold weather expected in ${row.city ?? location?.city ?? query.locationId}. Battery, winter fluid, wiper and tire demand may increase.`,
    };
  }

  if (heat) {
    return {
      sourceLabel: row.weather_source || row.weather_provider || "Cached Open-Meteo",
      isMock: false,
      location: row.city ?? location?.city ?? query.locationId,
      condition: "Warm weather signal",
      temperature: Math.round(temperature),
      affectedCategories: ["AC Cooling", "Coolant"],
      asOf: validDate(row.date),
      impact: `Warm weather expected in ${row.city ?? location?.city ?? query.locationId}. AC refill and coolant demand may increase.`,
    };
  }

  if (wet) {
    return {
      sourceLabel: row.weather_source || row.weather_provider || "Cached Open-Meteo",
      isMock: false,
      location: row.city ?? location?.city ?? query.locationId,
      condition: "Rain signal",
      temperature: Math.round(temperature),
      affectedCategories: ["Wipers", "Lighting", "Tires"],
      asOf: validDate(row.date),
      impact: `Rain expected in ${row.city ?? location?.city ?? query.locationId}. Wiper, lighting and tire checks may increase.`,
    };
  }

  return {
    sourceLabel: row.weather_source || row.weather_provider || "Cached Open-Meteo",
    isMock: false,
    location: row.city ?? location?.city ?? query.locationId,
    condition: "Stable weather",
    temperature: Math.round(temperature),
    affectedCategories: [forecastCategoryLabel(query.category)],
    asOf: validDate(row.date),
    impact: `No major weather spike is visible for ${row.city ?? location?.city ?? query.locationId}; demand should mostly follow historical and category patterns.`,
  };
}

export async function fetchWeatherImpact(query: ForecastQuery, signal?: AbortSignal): Promise<WeatherImpact> {
  const params = new URLSearchParams({
    location: query.locationId,
    limit: "16",
  });

  try {
    const response = await fetch(`/api/ml/weather/live?${params.toString()}`, {
      headers: authHeaders(),
      signal,
    });
    const data = (await response.json().catch(() => ({}))) as BackendListResponse<BackendWeatherRow>;
    const impact = response.ok && Array.isArray(data.items) ? normalizeWeatherImpact(data.items, query) : null;
    return impact ?? demoWeatherImpact(query);
  } catch {
    return demoWeatherImpact(query);
  }
}

export function displayPointDate(point: ForecastPoint) {
  return formatShortDate(point.date) || point.label;
}
