"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { MapData, MapFeature } from "../../lib/api";
import { EmptyState, LoadingSkeleton } from "../components/ui";

const API_URL =
  process.env.NEXT_PUBLIC_CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

const MapContainer = dynamic(
  () => import("react-leaflet").then((mod) => mod.MapContainer),
  { ssr: false },
);
const TileLayer = dynamic(
  () => import("react-leaflet").then((mod) => mod.TileLayer),
  { ssr: false },
);
const CircleMarker = dynamic(
  () => import("react-leaflet").then((mod) => mod.CircleMarker),
  { ssr: false },
);
const Popup = dynamic(() => import("react-leaflet").then((mod) => mod.Popup), {
  ssr: false,
});

const STATUS_COLORS: Record<string, string> = {
  publishable: "#087f5b",
  partial: "#e67700",
  no_data: "#868e96",
};

export default function MapPage() {
  const [data, setData] = useState<MapFeature[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [view, setView] = useState<"list" | "map">("list");

  useEffect(() => {
    const url = filter
      ? `${API_URL}/api/v1/facilities/map-data?pricing_status=${filter}`
      : `${API_URL}/api/v1/facilities/map-data`;
    fetch(url)
      .then((res) => res.json())
      .then((json: MapData) => {
        setData(json.features);
        setLoaded(true);
      })
      .catch(() => setError("Unable to load map data."));
  }, [filter]);

  return (
    <main style={{ maxWidth: "100%", padding: "1.5rem" }}>
      <p className="eyebrow">Explore by location</p>
      <h1 style={{ fontSize: "2.5rem" }}>Hospital map</h1>
      <p>
        Only facilities with published coordinates appear as markers. All
        facilities remain available in the hospital directory.
      </p>
      <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem" }}>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter by pricing availability"
          style={{
            padding: "0.5rem",
            border: "1px solid #9fb3ae",
            borderRadius: "0.5rem",
          }}
        >
          <option value="">All hospitals</option>
          <option value="publishable">With published prices</option>
          <option value="partial">Partial data</option>
          <option value="no_data">No pricing data</option>
        </select>
        <span
          style={{ fontSize: "0.85rem", color: "#526862", alignSelf: "center" }}
        >
          <span style={{ color: "#087f5b" }}>●</span> Published{" "}
          <span style={{ color: "#e67700" }}>●</span> Partial{" "}
          <span style={{ color: "#868e96" }}>●</span> No data
        </span>
        <div
          className="mobile-only"
          role="group"
          aria-label="Choose map or list view"
        >
          <button
            className={`button ${view === "list" ? "" : "secondary"}`}
            onClick={() => setView("list")}
          >
            List
          </button>
          <button
            className={`button ${view === "map" ? "" : "secondary"}`}
            onClick={() => setView("map")}
          >
            Map
          </button>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {!loaded && !error && <LoadingSkeleton />}
      {loaded && data.length === 0 && (
        <EmptyState title="No mapped hospitals match this filter">
          Try another price-availability filter. Hospitals without coordinates
          remain available in the directory.
        </EmptyState>
      )}
      {loaded && data.length > 0 && (
        <div className="map-shell">
          <section
            className={`map-list ${view === "map" ? "desktop-only" : ""}`}
            aria-label="Mapped hospitals"
          >
            <strong>{data.length} mapped hospitals</strong>
            <div className="result-list" style={{ marginTop: "1rem" }}>
              {data.map((feature) => (
                <article className="card" key={feature.properties.id}>
                  <span className="badge neutral">
                    {feature.properties.pricing_status.replaceAll("_", " ")}
                  </span>
                  <h2>
                    {feature.properties.location_name ??
                      feature.properties.name}
                  </h2>
                  {feature.properties.location_name && (
                    <p className="facility-parent">{feature.properties.name}</p>
                  )}
                  <p>
                    {feature.properties.city} ·{" "}
                    {feature.properties.procedure_count} published procedures
                  </p>
                  <Link
                    className="button secondary"
                    href={`/hospitals/${feature.properties.facility_id}`}
                  >
                    View details
                  </Link>
                </article>
              ))}
            </div>
          </section>
          <div
            className={`map-canvas ${view === "list" ? "desktop-only" : ""}`}
          >
            <MapContainer
              center={[43.45, -71.56]}
              zoom={8}
              style={{ height: "100%", width: "100%" }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {data.map((feature) => (
                <CircleMarker
                  key={feature.properties.id}
                  center={[
                    feature.geometry.coordinates[1],
                    feature.geometry.coordinates[0],
                  ]}
                  radius={8}
                  pathOptions={{
                    color:
                      STATUS_COLORS[feature.properties.pricing_status] ??
                      "#868e96",
                    fillColor:
                      STATUS_COLORS[feature.properties.pricing_status] ??
                      "#868e96",
                    fillOpacity: 0.7,
                  }}
                >
                  <Popup>
                    <strong>
                      {feature.properties.location_name ??
                        feature.properties.name}
                    </strong>
                    <br />
                    {feature.properties.city}
                    <br />
                    {feature.properties.procedure_count} procedures
                    <br />
                    <Link href={`/hospitals/${feature.properties.facility_id}`}>
                      View details →
                    </Link>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>
        </div>
      )}
    </main>
  );
}
