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

export const forecastHorizons: ForecastHorizon[] = [7, 14, 21];
export const mlForecastBaseUrl = process.env.NEXT_PUBLIC_ML_FORECAST_URL?.replace(/\/$/, "") ?? "";

export const forecastLocations: ForecastLocation[] = [
  { id: "RO_BUC", city: "Bucharest", climate: "Continental" },
  { id: "RO_CLJ", city: "Cluj-Napoca", climate: "Mountain edge" },
  { id: "RO_BRA", city: "Brasov", climate: "Mountain" },
  { id: "RO_TIM", city: "Timisoara", climate: "West plains" },
  { id: "RO_IAS", city: "Iasi", climate: "North-east" },
  { id: "RO_CTA", city: "Constanta", climate: "Coastal" },
];

export const forecastParts: ForecastPart[] = [
  { sku: "PEU-WINTER-TIRE-205", name: "Winter Tires 205/55 R16", category: "Tires" },
  { sku: "PEU-WF-WINTER-5L", name: "Winter Washer Fluid 5L", category: "Winter Fluids" },
  { sku: "PEU-BATT-70AH", name: "Battery 70Ah AGM/EFB", category: "Batteries" },
  { sku: "PEU-AC-REFILL", name: "AC Refill Kit R134a/R1234yf", category: "AC Cooling" },
  { sku: "PEU-CABIN-CARBON", name: "Cabin Carbon Filter", category: "Filters" },
  { sku: "PEU-BRK-PADS-208", name: "Brake Pads Peugeot 208", category: "Brakes" },
];

const locationMultiplier: Record<string, number> = {
  RO_BUC: 1.18,
  RO_CLJ: 1.08,
  RO_BRA: 1.16,
  RO_TIM: 1.04,
  RO_IAS: 1.1,
  RO_CTA: 0.98,
};

const categoryBase: Record<string, number> = {
  Tires: 34,
  "Winter Fluids": 42,
  Batteries: 18,
  "AC Cooling": 24,
  Filters: 28,
  Brakes: 31,
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
  return Boolean(mlForecastBaseUrl);
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
