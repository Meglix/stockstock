"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { BrainCircuit, CalendarDays, CloudSun, MapPin, PackageSearch, Sparkles, ThermometerSun } from "lucide-react";
import { DataPanel } from "../components/DataPanel";
import { DemandForecastChart } from "../components/DemandForecastChart";
import {
  BackendForecastResponse,
  ForecastHorizon,
  ForecastPoint,
  WeatherImpact,
  buildForecastInsight,
  fetchBackendForecastSeries,
  fetchWeatherImpact,
  forecastCategoryLabel,
  forecastHorizons,
  forecastLocations,
  forecastParts,
  forecastSourceLabel,
  getForecastCategories,
  getForecastSeries,
} from "../data/forecasting";
import { readCurrentUserLocation } from "../utils/userLocation";

function locationIdFromCity(city: string) {
  return forecastLocations.find((location) => location.city === city)?.id ?? "RO_BUC";
}

export function Forecasting() {
  const [initialLocation] = useState(() => locationIdFromCity(readCurrentUserLocation("Bucharest")));
  const [locationId, setLocationId] = useState(initialLocation);
  const [category, setCategory] = useState("Tires");
  const filteredParts = useMemo(() => forecastParts.filter((part) => part.category === category), [category]);
  const [sku, setSku] = useState("PEU-WINTER-TIRE-205");
  const [horizon, setHorizon] = useState<ForecastHorizon>(14);
  const categories = useMemo(() => getForecastCategories(), []);
  const selectedPart = forecastParts.find((part) => part.sku === sku) ?? filteredParts[0] ?? forecastParts[0];
  const selectedLocation = forecastLocations.find((location) => location.id === locationId) ?? forecastLocations[0];
  const [backendPoints, setBackendPoints] = useState<ForecastPoint[]>([]);
  const [forecastResponse, setForecastResponse] = useState<BackendForecastResponse | null>(null);
  const [forecastError, setForecastError] = useState("");
  const [forecastWarnings, setForecastWarnings] = useState<string[]>([]);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [weatherImpact, setWeatherImpact] = useState<WeatherImpact | null>(null);

  const fallbackPoints = useMemo(
    () =>
      getForecastSeries({
        locationId,
        category,
        sku: selectedPart.sku,
        horizon,
      }),
    [category, horizon, locationId, selectedPart.sku],
  );
  const points = backendPoints.length ? backendPoints : forecastResponse?.available ? [] : fallbackPoints;
  const displayCategory = forecastCategoryLabel(category);
  const sourceLabel = forecastResponse ? forecastSourceLabel(forecastResponse) : "Local fallback";
  const chartTitle = `Demand forecast for ${displayCategory} in ${selectedLocation.city} - next ${horizon} days`;

  useEffect(() => {
    const controller = new AbortController();

    setForecastLoading(true);
    setForecastError("");

    void fetchBackendForecastSeries(
      {
        locationId,
        category,
        sku: selectedPart.sku,
        horizon,
      },
      controller.signal,
    )
      .then(({ points: nextPoints, response, warnings }) => {
        if (controller.signal.aborted) return;
        setBackendPoints(nextPoints);
        setForecastResponse(response);
        setForecastWarnings(warnings);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setBackendPoints([]);
        setForecastResponse(null);
        setForecastWarnings([]);
        setForecastError(error instanceof Error ? error.message : "Forecast data is unavailable.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setForecastLoading(false);
      });

    return () => controller.abort();
  }, [category, horizon, locationId, selectedPart.sku]);

  useEffect(() => {
    const controller = new AbortController();
    void fetchWeatherImpact(
      {
        locationId,
        category,
        sku: selectedPart.sku,
        horizon,
      },
      controller.signal,
    ).then((impact) => {
      if (!controller.signal.aborted) setWeatherImpact(impact);
    });
    return () => controller.abort();
  }, [category, horizon, locationId, selectedPart.sku]);

  const insight = useMemo(
    () =>
      buildForecastInsight(
        {
          locationId,
          category,
          sku: selectedPart.sku,
          horizon,
        },
        points,
      ),
    [category, horizon, locationId, points, selectedPart.sku],
  );
  const forecastWindow = points.filter((point) => typeof point.forecast === "number").slice(0, horizon);
  const totalForecast = forecastWindow.reduce((sum, point) => sum + (point.forecast ?? 0), 0);
  const peakDay = forecastWindow.reduce<ForecastPoint | null>((best, point) => (!best || (point.forecast ?? 0) > (best.forecast ?? 0) ? point : best), null);

  const handleCategoryChange = (nextCategory: string) => {
    setCategory(nextCategory);
    const nextPart = forecastParts.find((part) => part.category === nextCategory);
    if (nextPart) setSku(nextPart.sku);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="space-y-5">
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <DataPanel
          title={chartTitle}
          eyebrow="Forecast command center"
          action={
            <span className="panel-pill">
              <BrainCircuit size={13} />
              {forecastLoading ? "Loading forecast" : sourceLabel}
            </span>
          }
        >
          <p className="mb-4 text-sm leading-6 text-slate-400">
            Forecast uses historical sales, selected location, category demand, and ML weather features where available. The weather card below shows cached Open-Meteo data when present, otherwise an explicit demo weather signal.
          </p>
          <div className="mb-4 flex flex-wrap gap-2">
            <span className="panel-pill"><MapPin size={13} /> {selectedLocation.city}</span>
            <span className="panel-pill"><PackageSearch size={13} /> {displayCategory}</span>
            <span className="panel-pill">{selectedPart.name}</span>
            <span className="panel-pill"><CalendarDays size={13} /> {horizon} days</span>
          </div>
          <div className="forecast-control-grid mb-5">
            <label className="form-field">
              <span>Location</span>
              <div className="input-shell">
                <MapPin size={16} />
                <select value={locationId} onChange={(event) => setLocationId(event.target.value)}>
                  {forecastLocations.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.city}
                    </option>
                  ))}
                </select>
              </div>
            </label>

            <label className="form-field">
              <span>Category</span>
              <div className="input-shell">
                <PackageSearch size={16} />
                <select value={category} onChange={(event) => handleCategoryChange(event.target.value)}>
                  {categories.map((item) => (
                    <option key={item} value={item}>{forecastCategoryLabel(item)}</option>
                  ))}
                </select>
              </div>
            </label>

            <label className="form-field">
              <span>Part</span>
              <div className="input-shell">
                <PackageSearch size={16} />
                <select value={selectedPart.sku} onChange={(event) => setSku(event.target.value)}>
                  {filteredParts.map((part) => (
                    <option key={part.sku} value={part.sku}>
                      {part.name}
                    </option>
                  ))}
                </select>
              </div>
            </label>
          </div>

          <DemandForecastChart points={points} horizon={horizon} onHorizonChange={setHorizon} emptyMessage={forecastWarnings[0] || forecastError || "Not enough data for a connected forecast line."} />
        </DataPanel>

        <div className="space-y-5">
          <DataPanel title="AI Forecast Insight" eyebrow="Plain language summary" action={<span className="panel-pill"><Sparkles size={13} /> LLM-ready</span>}>
            <div className="rounded-xl border border-orange-300/16 bg-orange-400/[0.055] p-4">
              <p className="text-sm leading-6 text-slate-300">{insight}</p>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <div className="detail-tile">
                <span>Selected location</span>
                <strong>{selectedLocation.city}</strong>
              </div>
              <div className="detail-tile">
                <span>Climate signal</span>
                <strong>{selectedLocation.climate}</strong>
              </div>
              <div className="detail-tile">
                <span>{horizon}-day forecast</span>
                <strong>{Math.round(totalForecast).toLocaleString()} units</strong>
              </div>
              <div className="detail-tile">
                <span>Peak forecast day</span>
                <strong>{peakDay ? `${peakDay.label} / ${peakDay.forecast} units` : "Not enough data"}</strong>
              </div>
            </div>
          </DataPanel>

          <DataPanel title="Weather Impact" eyebrow={weatherImpact?.sourceLabel ?? "Weather signal"} action={<span className="panel-pill"><CloudSun size={13} /> {weatherImpact?.isMock ? "Demo" : "Cached"}</span>}>
            {weatherImpact ? (
              <>
                <div className="rounded-xl border border-sky-300/16 bg-sky-400/[0.055] p-4">
                  <div className="flex items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-sky-300/20 bg-sky-400/10 text-sky-100">
                      <ThermometerSun size={18} />
                    </span>
                    <div>
                      <p className="font-bold text-white">{weatherImpact.condition}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-300">{weatherImpact.impact}</p>
                    </div>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-1">
                  <div className="detail-tile"><span>Location</span><strong>{weatherImpact.location}</strong></div>
                  <div className="detail-tile"><span>Temperature</span><strong>{weatherImpact.temperature} C</strong></div>
                  <div className="detail-tile"><span>Affected categories</span><strong>{weatherImpact.affectedCategories.join(", ")}</strong></div>
                  <div className="detail-tile"><span>Signal date</span><strong>{weatherImpact.asOf ?? "Demo fallback"}</strong></div>
                </div>
              </>
            ) : (
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.025] px-4 py-8 text-center text-sm text-slate-500">Loading weather signal...</div>
            )}
          </DataPanel>

          <DataPanel title="Forecast Horizon" eyebrow="Scenario control" action={<span className="panel-pill"><CalendarDays size={13} /> {horizon} days</span>}>
            <div className="segmented-tabs forecast-horizon-tabs w-full">
              {forecastHorizons.map((item) => (
                <button key={item} type="button" className={horizon === item ? "is-active" : ""} onClick={() => setHorizon(item)}>
                  {item} days
                </button>
              ))}
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-500">
              {forecastWarnings[0] || (forecastResponse?.error && backendPoints.length ? forecastResponse.error : forecastError || `The ${horizon}-day horizon changes the forecast range, chart title, totals, and insight text.`)}
            </p>
          </DataPanel>
        </div>
      </section>
    </motion.div>
  );
}
