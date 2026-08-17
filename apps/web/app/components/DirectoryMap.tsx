"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { MapData, MapFeature } from "../../lib/api";
import { localePath, type Locale } from "../../lib/i18n";
import type { DirectoryStrings } from "../../lib/directory-i18n";

const MapContainer = dynamic(() => import("react-leaflet").then((m) => m.MapContainer), {
  ssr: false,
});
const TileLayer = dynamic(() => import("react-leaflet").then((m) => m.TileLayer), { ssr: false });
const CircleMarker = dynamic(() => import("react-leaflet").then((m) => m.CircleMarker), {
  ssr: false,
});
const Popup = dynamic(() => import("react-leaflet").then((m) => m.Popup), { ssr: false });

const STATUS_COLORS: Record<string, string> = {
  pricing_available: "#0961dc",
  limited_pricing: "#e67700",
  pricing_not_available_yet: "#868e96",
};

/**
 * Map view for the Provider Directory. Fetches the SAME filtered dataset (state +
 * capability + region) via a same-origin proxy, so it works on any web origin and
 * reflects the active provider-type/region filters. Pins are real service locations
 * only — never fabricated.
 */
export function DirectoryMap({
  locale,
  t,
  state,
  capability,
  region,
  center,
  zoom,
  detailBase,
}: {
  locale: Locale;
  t: DirectoryStrings;
  state: string;
  capability: string;
  region: string;
  center: [number, number];
  zoom: number;
  detailBase: string;
}) {
  const [features, setFeatures] = useState<MapFeature[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    const query = new URLSearchParams({ state });
    if (capability) query.set("capability", capability);
    if (region) query.set("region", region);
    let cancelled = false;
    setStatus("loading");
    fetch(`/api/providers/map?${query}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("map failed"))))
      .then((json: MapData) => {
        if (cancelled) return;
        setFeatures(json.features ?? []);
        setStatus("ok");
      })
      .catch(() => !cancelled && setStatus("error"));
    return () => {
      cancelled = true;
    };
  }, [state, capability, region]);

  if (status === "error") {
    return <p className="pd-map-msg error">{t.mapUnavailable}</p>;
  }

  return (
    <div className="pd-map-canvas">
      <MapContainer center={center} zoom={zoom} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {features.map((f) => (
          <CircleMarker
            key={f.properties.id}
            center={[f.geometry.coordinates[1], f.geometry.coordinates[0]]}
            radius={8}
            pathOptions={{
              color: STATUS_COLORS[f.properties.pricing_status] ?? "#868e96",
              fillColor: STATUS_COLORS[f.properties.pricing_status] ?? "#868e96",
              fillOpacity: 0.7,
            }}
          >
            <Popup>
              <strong>{f.properties.location_name ?? f.properties.name}</strong>
              <br />
              {f.properties.city}
              <br />
              <Link href={localePath(locale, `${detailBase}/${f.properties.facility_id}`)}>
                {t.viewProvider} →
              </Link>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
