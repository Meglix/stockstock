"use client";

import type { CSSProperties } from "react";
import Link from "next/link";

const menuItems = ["Parts", "Stocks", "Orders", "AI Agent"];

const tickAngles = [0, 45, 90, 135, 180, 225, 270, 315];

function Dial({ value, unit, label }: { value: string; unit: string; label: string }) {
  return (
    <div className="intro-dial" aria-label={label}>
      {tickAngles.map((angle) => (
        <span
          aria-hidden="true"
          className="intro-dial-tick"
          key={angle}
          style={{ "--angle": `${angle}deg` } as CSSProperties}
        />
      ))}
      <div className="intro-dial-center">
        <span className="intro-dial-value">{value}</span>
        <span className="intro-dial-unit">{unit}</span>
      </div>
    </div>
  );
}

export function Intro() {
  return (
    <main className="intro-screen">
      <img src="/automotive-interface.jpg" alt="" className="intro-reference-glow" />
      <div className="intro-backdrop" />
      <div className="intro-vignette" />
      <div className="noise-overlay" />

      <section className="intro-shell" aria-label="Stock Optimizer start page">
        <div className="intro-brand">
          <img className="intro-brand-logo" src="/autoparts-stock-optimizer-logo-transparent.png" alt="AutoParts Stock Optimizer by RRParts" />
        </div>

        <div className="intro-cockpit">
          <Dial value="20" unit="RPMX100" label="Engine speed 20 RPM times 100" />

          <div className="intro-menu" aria-label="Start page status">
            <span>{menuItems[0]}</span>
            <span>{menuItems[1]}</span>
            <Link className="intro-enter-button" href="/login">
              Enter website
            </Link>
            <span>{menuItems[2]}</span>
            <span>{menuItems[3]}</span>
          </div>

          <Dial value="80" unit="km/h" label="Vehicle speed 80 kilometers per hour" />

          <span className="intro-stat intro-stat-temp">
            22<sup>o</sup>C
          </span>
          <span className="intro-stat intro-stat-distance">1000km</span>
        </div>
      </section>
    </main>
  );
}
