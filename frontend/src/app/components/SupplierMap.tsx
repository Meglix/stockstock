"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { LocateFixed, MapPin, Minus, Plus } from "lucide-react";
import worldAtlas from "../data/countries-110m.json";
import { SupplierLocation, supplierLocations } from "../data/inventory";

const MAP_WIDTH = 1000;
const MAP_HEIGHT = 500;
const longitudeLines = [125, 250, 375, 500, 625, 750, 875];
const latitudeLines = [100, 175, 250, 325, 400];

type CountryGeometry = {
  type: "Polygon" | "MultiPolygon";
  arcs: number[][] | number[][][];
  properties?: { name?: string };
};

type WorldTopology = {
  transform: {
    scale: [number, number];
    translate: [number, number];
  };
  arcs: number[][][];
  objects: {
    countries: {
      geometries: CountryGeometry[];
    };
  };
};

type Coordinate = [number, number];

function projectPoint([longitude, latitude]: Coordinate): Coordinate {
  return [((longitude + 180) / 360) * MAP_WIDTH, ((90 - latitude) / 180) * MAP_HEIGHT];
}

function buildCountryPaths(topology: WorldTopology) {
  const { scale, translate } = topology.transform;
  const decodedArcs = topology.arcs.map((arc) => {
    let x = 0;
    let y = 0;
    return arc.map(([dx, dy]) => {
      x += dx;
      y += dy;
      return [x * scale[0] + translate[0], y * scale[1] + translate[1]] as Coordinate;
    });
  });

  const getArc = (index: number) => {
    const arc = decodedArcs[index < 0 ? ~index : index] ?? [];
    return index < 0 ? [...arc].reverse() : arc;
  };

  const ringToPath = (ring: number[]) => {
    const points = ring.flatMap((arcIndex, index) => {
      const arc = getArc(arcIndex);
      return index === 0 ? arc : arc.slice(1);
    });
    if (points.length < 3) return "";

    return points
      .map((point, index) => {
        const [x, y] = projectPoint(point);
        return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
  };

  return topology.objects.countries.geometries
    .map((geometry, index) => {
      const polygons = geometry.type === "Polygon" ? [geometry.arcs as number[][]] : (geometry.arcs as number[][][]);
      const d = polygons
        .flatMap((polygon) => polygon.map(ringToPath))
        .filter(Boolean)
        .map((path) => `${path} Z`)
        .join(" ");
      return { id: `${geometry.properties?.name ?? "country"}-${index}`, d };
    })
    .filter((country) => country.d);
}

const countryPaths = buildCountryPaths(worldAtlas as unknown as WorldTopology);

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

export function SupplierMap({ locations = supplierLocations }: { locations?: SupplierLocation[] }) {
  const activeLocations = locations.length ? locations : supplierLocations;
  const centerX = activeLocations.reduce((sum, location) => sum + location.x, 0) / activeLocations.length;
  const centerY = activeLocations.reduce((sum, location) => sum + location.y, 0) / activeLocations.length;
  const centeredView = (zoomValue: number) => {
    const width = MAP_WIDTH / zoomValue;
    const height = MAP_HEIGHT / zoomValue;
    return {
      x: clamp(centerX - width / 2, 0, MAP_WIDTH - width),
      y: clamp(centerY - height / 2, 0, MAP_HEIGHT - height),
    };
  };
  const [active, setActive] = useState(activeLocations[0]);
  const [zoom, setZoom] = useState(2.1);
  const [viewOrigin, setViewOrigin] = useState(() => centeredView(2.1));
  const [isDragging, setIsDragging] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number; moved: boolean } | null>(null);
  const hub = activeLocations.find((location) => /hub|rrparts/i.test(location.supplier)) ?? activeLocations[0];
  const activeCatalogParts = active.catalog_parts ?? active.parts;
  const activeUnits = active.available_units;
  const viewWidth = MAP_WIDTH / zoom;
  const viewHeight = MAP_HEIGHT / zoom;
  const viewX = clamp(viewOrigin.x, 0, MAP_WIDTH - viewWidth);
  const viewY = clamp(viewOrigin.y, 0, MAP_HEIGHT - viewHeight);

  useEffect(() => {
    setActive(activeLocations[0]);
    setZoom(2.1);
    setViewOrigin(centeredView(2.1));
  }, [activeLocations, centerX, centerY]);

  const markerLabel = (location: SupplierLocation) => (location.country_code || location.country.slice(0, 2)).toUpperCase();
  const setClampedOrigin = (x: number, y: number, zoomValue = zoom) => {
    const width = MAP_WIDTH / zoomValue;
    const height = MAP_HEIGHT / zoomValue;
    setViewOrigin({
      x: clamp(x, 0, MAP_WIDTH - width),
      y: clamp(y, 0, MAP_HEIGHT - height),
    });
  };
  const zoomTo = (nextZoomValue: number, anchor?: { clientX: number; clientY: number }) => {
    setZoom((currentZoom) => {
      const nextZoom = clamp(Number(nextZoomValue.toFixed(2)), 1, 3.2);
      setViewOrigin((origin) => {
        const currentWidth = MAP_WIDTH / currentZoom;
        const currentHeight = MAP_HEIGHT / currentZoom;
        const nextWidth = MAP_WIDTH / nextZoom;
        const nextHeight = MAP_HEIGHT / nextZoom;
        const rect = svgRef.current?.getBoundingClientRect();

        if (anchor && rect) {
          const ratioX = clamp((anchor.clientX - rect.left) / rect.width, 0, 1);
          const ratioY = clamp((anchor.clientY - rect.top) / rect.height, 0, 1);
          const mapX = origin.x + ratioX * currentWidth;
          const mapY = origin.y + ratioY * currentHeight;
          return {
            x: clamp(mapX - ratioX * nextWidth, 0, MAP_WIDTH - nextWidth),
            y: clamp(mapY - ratioY * nextHeight, 0, MAP_HEIGHT - nextHeight),
          };
        }

        const mapCenterX = origin.x + currentWidth / 2;
        const mapCenterY = origin.y + currentHeight / 2;
        return {
          x: clamp(mapCenterX - nextWidth / 2, 0, MAP_WIDTH - nextWidth),
          y: clamp(mapCenterY - nextHeight / 2, 0, MAP_HEIGHT - nextHeight),
        };
      });
      return nextZoom;
    });
  };
  const resetView = () => {
    setZoom(2.1);
    setViewOrigin(centeredView(2.1));
  };

  return (
    <div className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-[#06080d]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_54%_39%,rgba(249,115,22,0.13),transparent_22%),linear-gradient(180deg,rgba(255,255,255,0.04),transparent)]" />
      <div className="absolute left-4 top-4 z-10 rounded-full border border-orange-300/20 bg-orange-400/10 px-3 py-1 text-xs font-semibold uppercase text-orange-200">
        Global supplier network
      </div>
      <div className="absolute right-4 top-4 z-10 flex items-center gap-2">
        <button
          type="button"
          title="Zoom out"
          aria-label="Zoom out"
          onClick={() => zoomTo(zoom - 0.35)}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.1] bg-black/45 text-slate-300 transition hover:border-orange-300/28 hover:text-orange-200"
        >
          <Minus size={15} />
        </button>
        <button
          type="button"
          title="Center supplier region"
          aria-label="Center supplier region"
          onClick={resetView}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.1] bg-black/45 text-slate-300 transition hover:border-orange-300/28 hover:text-orange-200"
        >
          <LocateFixed size={15} />
        </button>
        <button
          type="button"
          title="Zoom in"
          aria-label="Zoom in"
          onClick={() => zoomTo(zoom + 0.35)}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.1] bg-black/45 text-slate-300 transition hover:border-orange-300/28 hover:text-orange-200"
        >
          <Plus size={15} />
        </button>
      </div>

      <svg
        ref={svgRef}
        viewBox={`${viewX} ${viewY} ${viewWidth} ${viewHeight}`}
        className={`relative h-[330px] w-full select-none md:h-[390px] ${isDragging ? "cursor-grabbing" : "cursor-grab"}`}
        role="img"
        aria-label="World supplier map"
        style={{ touchAction: "none" }}
        onWheel={(event) => {
          event.preventDefault();
          zoomTo(zoom + (event.deltaY > 0 ? -0.18 : 0.18), event);
        }}
        onPointerDown={(event) => {
          dragRef.current = {
            pointerId: event.pointerId,
            startX: event.clientX,
            startY: event.clientY,
            originX: viewX,
            originY: viewY,
            moved: false,
          };
          event.currentTarget.setPointerCapture(event.pointerId);
          setIsDragging(true);
        }}
        onPointerMove={(event) => {
          const drag = dragRef.current;
          const rect = svgRef.current?.getBoundingClientRect();
          if (!drag || !rect) return;
          const dx = ((event.clientX - drag.startX) * viewWidth) / rect.width;
          const dy = ((event.clientY - drag.startY) * viewHeight) / rect.height;
          drag.moved = drag.moved || Math.abs(event.clientX - drag.startX) > 3 || Math.abs(event.clientY - drag.startY) > 3;
          setClampedOrigin(drag.originX - dx, drag.originY - dy);
        }}
        onPointerUp={(event) => {
          const drag = dragRef.current;
          if (drag?.pointerId === event.pointerId) {
            dragRef.current = null;
            event.currentTarget.releasePointerCapture(event.pointerId);
            setIsDragging(false);
          }
        }}
        onPointerCancel={() => {
          dragRef.current = null;
          setIsDragging(false);
        }}
      >
        <defs>
          <linearGradient id="landGradient" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#94a3b8" stopOpacity="0.34" />
            <stop offset="54%" stopColor="#334155" stopOpacity="0.42" />
            <stop offset="100%" stopColor="#111827" stopOpacity="0.55" />
          </linearGradient>
          <filter id="orangeGlow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect width="1000" height="500" fill="#06080d" />
        {longitudeLines.map((x) => (
          <path key={`lon-${x}`} d={`M ${x} 38 C ${x - 18} 142 ${x - 18} 358 ${x} 462`} fill="none" stroke="rgba(148,163,184,0.12)" strokeWidth="0.8" />
        ))}
        {latitudeLines.map((y) => (
          <path key={`lat-${y}`} d={`M 64 ${y} C 248 ${y - 20} 742 ${y - 20} 936 ${y}`} fill="none" stroke="rgba(148,163,184,0.11)" strokeWidth="0.8" />
        ))}
        <ellipse cx="500" cy="250" rx="438" ry="212" fill="none" stroke="rgba(255,255,255,0.075)" />
        <line x1="62" x2="938" y1="250" y2="250" stroke="rgba(255,255,255,0.075)" />

        {countryPaths.map((country) => (
          <path
            key={country.id}
            d={country.d}
            fill="url(#landGradient)"
            fillRule="evenodd"
            stroke="rgba(255,255,255,0.16)"
            strokeWidth="0.55"
            opacity="0.78"
          />
        ))}

        {activeLocations
          .filter((location) => location.supplier !== hub.supplier)
          .map((location) => (
            <path
              key={`route-${location.supplier}`}
              d={`M ${hub.x} ${hub.y} C ${(hub.x + location.x) / 2} ${Math.min(hub.y, location.y) - 34}, ${(hub.x + location.x) / 2} ${Math.min(hub.y, location.y) - 34}, ${location.x} ${location.y}`}
              stroke="rgba(249,115,22,0.28)"
              strokeWidth="1.4"
              strokeDasharray="5 8"
              fill="none"
            />
          ))}

        {activeLocations.map((location, index) => (
          <g key={`${location.country}-${location.supplier}`} onMouseEnter={() => setActive(location)} onClick={() => setActive(location)} className="cursor-pointer">
            <motion.circle
              cx={location.x}
              cy={location.y}
              r="12"
              fill="rgba(249,115,22,0.18)"
              animate={{ r: [10, 24], opacity: [0.65, 0] }}
              transition={{ duration: 2.2, repeat: Infinity, delay: index * 0.22 }}
            />
            <circle cx={location.x} cy={location.y} r={active.supplier === location.supplier ? 7 : 5} fill="#fb923c" filter="url(#orangeGlow)" />
            <circle cx={location.x} cy={location.y} r="2" fill="#fff7ed" />
            <text x={location.x} y={location.y - 15} textAnchor="middle" fill="#fed7aa" fontSize="10" fontWeight="700" opacity={active.supplier === location.supplier ? 0.95 : 0.62}>
              {markerLabel(location)}
            </text>
          </g>
        ))}
      </svg>

      <motion.div
        key={active.supplier}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="absolute bottom-4 left-4 right-4 flex flex-col gap-3 rounded-xl border border-white/10 bg-black/58 p-4 backdrop-blur-xl md:left-auto md:w-[310px]"
      >
        <div className="flex items-start gap-3">
          <div className="rounded-lg border border-orange-300/25 bg-orange-400/12 p-2 text-orange-200">
            <MapPin size={18} />
          </div>
          <div>
            <p className="text-sm font-bold text-white">{active.supplier}</p>
            <p className="text-xs text-slate-400">
              {active.city}, {active.country}
            </p>
          </div>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-400">Catalog parts</span>
          <span className="font-black text-orange-200">{activeCatalogParts.toLocaleString()}</span>
        </div>
        {typeof activeUnits === "number" ? (
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">Local stock units</span>
            <span className="font-black text-orange-200">{activeUnits.toLocaleString()}</span>
          </div>
        ) : null}
      </motion.div>
    </div>
  );
}
