"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { MapData, MapFeature } from "../../lib/api";
import { EmptyState, LoadingSkeleton } from "../components/ui";
import { launchRegion } from "../../lib/brand";
import { localePath, messages } from "../../lib/i18n";
import { useLocale } from "../components/useLocale";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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
  pricing_available: "#087f5b",
  limited_pricing: "#e67700",
  pricing_not_available_yet: "#868e96",
};

export default function MapPage() {
  const locale = useLocale();
  const t = messages[locale] ?? messages.en;
  const statusLabels: Record<string, string> = {
    pricing_available: t.mapPricingAvailable,
    limited_pricing: t.mapLimitedPricing,
    pricing_not_available_yet: t.mapNotAvailableYet,
  };
  const [data, setData] = useState<MapFeature[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [view, setView] = useState<"list" | "map">("list");

  useEffect(() => {
    const query = new URLSearchParams({ state: launchRegion.state });
    if (filter) query.set("pricing_status", filter);
    const url = `${API_URL}/api/v1/facilities/map-data?${query}`;
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error("map request failed");
        return res.json();
      })
      .then((json: MapData) => {
        setData(json.features);
        setLoaded(true);
      })
      .catch(() => setError(t.mapUnableToLoad));
  }, [filter, t.mapUnableToLoad]);

  return (
    <main style={{ maxWidth: "100%", padding: "1.5rem" }}>
      <p className="eyebrow">{t.mapExploreByLocation}</p>
      <h1 style={{ fontSize: "2.5rem" }}>{t.mapTitle}</h1>
      <p>{t.mapIntro}</p>
      <div style={{ marginBottom: "1rem", display: "flex", gap: "0.5rem" }}>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label={t.mapFilterAria}
          style={{
            padding: "0.5rem",
            border: "1px solid #9fb3ae",
            borderRadius: "0.5rem",
          }}
        >
          <option value="">{t.availabilityAll}</option>
          <option value="pricing_available">{t.mapPricingAvailable}</option>
          <option value="limited_pricing">{t.mapLimitedPricing}</option>
          <option value="pricing_not_available_yet">
            {t.mapNotAvailableYet}
          </option>
        </select>
        <span
          style={{ fontSize: "0.85rem", color: "#526862", alignSelf: "center" }}
        >
          <span style={{ color: "#087f5b" }}>●</span> {t.mapLegendAvailable}{" "}
          <span style={{ color: "#e67700" }}>●</span> {t.mapLegendLimited}{" "}
          <span style={{ color: "#868e96" }}>●</span> {t.mapLegendNotYet}
        </span>
        <div
          className="mobile-only"
          role="group"
          aria-label={t.mapViewGroupAria}
        >
          <button
            className={`button ${view === "list" ? "" : "secondary"}`}
            onClick={() => setView("list")}
          >
            {t.mapListView}
          </button>
          <button
            className={`button ${view === "map" ? "" : "secondary"}`}
            onClick={() => setView("map")}
          >
            {t.mapMapView}
          </button>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {!loaded && !error && <LoadingSkeleton messages={t} />}
      {loaded && data.length === 0 && (
        <EmptyState title={t.mapNoMatchTitle}>{t.mapNoMatchBody}</EmptyState>
      )}
      {loaded && data.length > 0 && (
        <div className="map-shell">
          <section
            className={`map-list ${view === "map" ? "desktop-only" : ""}`}
            aria-label={t.mapMappedHospitalsAria}
          >
            <strong>
              {t.mapMappedHospitalsCount.replace("{count}", String(data.length))}
            </strong>
            <div className="result-list" style={{ marginTop: "1rem" }}>
              {data.map((feature) => (
                <article className="card" key={feature.properties.id}>
                  <span className="badge neutral">
                    {statusLabels[feature.properties.pricing_status] ??
                      t.mapPricingStatusUnavailable}
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
                    {t.mapPublishedProceduresCount.replace(
                      "{count}",
                      String(feature.properties.procedure_count),
                    )}
                  </p>
                  <Link
                    className="button secondary"
                    href={localePath(
                      locale,
                      `/hospitals/${feature.properties.facility_id}`,
                    )}
                  >
                    {t.viewDetails}
                  </Link>
                </article>
              ))}
            </div>
          </section>
          <div
            className={`map-canvas ${view === "list" ? "desktop-only" : ""}`}
          >
            <MapContainer
              center={launchRegion.mapCenter}
              zoom={launchRegion.mapZoom}
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
                    {t.mapProceduresCount.replace(
                      "{count}",
                      String(feature.properties.procedure_count),
                    )}
                    <br />
                    <Link
                      href={localePath(
                        locale,
                        `/hospitals/${feature.properties.facility_id}`,
                      )}
                    >
                      {t.viewDetails} →
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
