"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { FacilityProcedureOverviewItem } from "../../lib/api";
import { PriceRange, SourceAttribution } from "./ui";

export function FacilityPrices({
  items,
}: {
  items: FacilityProcedureOverviewItem[];
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return items;
    return items.filter((item) =>
      `${item.procedure_name} ${item.location_name ?? ""} ${item.city ?? ""}`
        .toLowerCase()
        .includes(normalized),
    );
  }, [items, query]);
  return (
    <>
      <div className="table-search field">
        <label htmlFor="facility-price-search">
          Search available procedures
        </label>
        <input
          id="facility-price-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="MRI, lab test, location…"
        />
        <span className="field-help" role="status">
          {filtered.length} published result{filtered.length === 1 ? "" : "s"}
        </span>
      </div>
      {filtered.length ? (
        <div className="table-wrap">
          <table className="price-table">
            <thead>
              <tr>
                <th scope="col">Procedure and location</th>
                <th scope="col">Cash price</th>
                <th scope="col">Insurance pricing</th>
                <th scope="col">Setting</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((price) => (
                <tr
                  key={`${price.procedure_slug}-${price.facility_location_id}`}
                >
                  <td data-label="Procedure and location">
                    <Link href={`/procedures/${price.procedure_slug}/prices`}>
                      {price.procedure_name}
                    </Link>
                    <small>
                      {price.location_name ??
                        price.city ??
                        "Location not labeled"}
                    </small>
                  </td>
                  <td data-label="Cash price">
                    <PriceRange
                      min={price.cash_price_min}
                      max={price.cash_price_max}
                    />
                  </td>
                  <td data-label="Insurance pricing">
                    {price.negotiated_price_min !== null ? (
                      <Link href={`/procedures/${price.procedure_slug}/prices`}>
                        Published rates available — choose a payer
                      </Link>
                    ) : (
                      "No normalized payer rates published"
                    )}
                  </td>
                  <td data-label="Setting">
                    {price.service_settings.join(", ").replaceAll("_", " ")}
                  </td>
                  <td data-label="Source">
                    <SourceAttribution
                      updated={price.latest_updated}
                      url={price.source_url}
                      showLink={false}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="inline-empty">
          No published procedures match this search.
        </p>
      )}
    </>
  );
}
