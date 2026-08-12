"use client";

import Link from "next/link";
import { useMemo, useSyncExternalStore } from "react";
import type { ProcedureComparisonItem } from "../../lib/api";
import { FacilityImage } from "./FacilityImage";

interface CompareChoice {
  key: string;
  facilityId: string;
  locationId: string;
  name: string;
}

function storageKey(procedureSlug: string) {
  return `careveroCompareV1:${procedureSlug}`;
}

function parseChoices(value: string): CompareChoice[] {
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) ? (parsed as CompareChoice[]).slice(0, 3) : [];
  } catch {
    return [];
  }
}

function subscribe(onStoreChange: () => void) {
  window.addEventListener("carevero:selection", onStoreChange);
  return () => window.removeEventListener("carevero:selection", onStoreChange);
}

function useChoices(procedureSlug: string) {
  const serialized = useSyncExternalStore(
    subscribe,
    () => sessionStorage.getItem(storageKey(procedureSlug)) ?? "[]",
    () => "[]",
  );
  return useMemo(() => parseChoices(serialized), [serialized]);
}

export function CompareSelect({
  facilityId,
  locationId,
  name,
  procedureSlug,
}: {
  facilityId: string;
  locationId: string;
  name: string;
  procedureSlug: string;
}) {
  const key = `${facilityId}~${locationId}`;
  const selected = useChoices(procedureSlug);
  const active = selected.some((choice) => choice.key === key);
  const limitReached = !active && selected.length >= 3;

  function toggle() {
    const current = parseChoices(
      sessionStorage.getItem(storageKey(procedureSlug)) ?? "[]",
    );
    const currentlyActive = current.some((choice) => choice.key === key);
    const next = currentlyActive
      ? current.filter((choice) => choice.key !== key)
      : current.length < 3
        ? [...current, { key, facilityId, locationId, name }]
        : current;
    sessionStorage.setItem(storageKey(procedureSlug), JSON.stringify(next));
    window.dispatchEvent(new Event("carevero:selection"));
  }

  return (
    <div className="compare-actions">
      <button
        type="button"
        className="button secondary"
        onClick={toggle}
        disabled={limitReached}
        aria-pressed={active}
        aria-label={`${active ? "Remove" : "Add"} ${name} ${active ? "from" : "to"} comparison`}
      >
        {active
          ? "✓ Selected"
          : limitReached
            ? "3 selected — remove one to add"
            : "+ Compare"}
      </button>
    </div>
  );
}

export function CompareTray({
  procedureSlug,
  payer,
  plan,
}: {
  procedureSlug: string;
  payer?: string;
  plan?: string;
}) {
  const selected = useChoices(procedureSlug);

  if (selected.length === 0) return null;
  const compareQuery = new URLSearchParams({
    items: selected.map((choice) => choice.key).join(","),
    procedure: procedureSlug,
  });
  if (payer) compareQuery.set("payer", payer);
  if (plan) compareQuery.set("plan", plan);
  const compareHref = `/compare?${compareQuery}`;
  function clear() {
    sessionStorage.removeItem(storageKey(procedureSlug));
    window.dispatchEvent(new Event("carevero:selection"));
  }
  return (
    <aside className="compare-tray" aria-live="polite">
      <div>
        <strong>Compare hospitals · {selected.length} of 3 selected</strong>
        <ul aria-label="Selected locations">
          {selected.map((choice) => (
            <li key={choice.key}>{choice.name}</li>
          ))}
        </ul>
      </div>
      <button className="text-button" type="button" onClick={clear}>
        Clear
      </button>
      {selected.length >= 2 ? (
        <Link className="button" href={compareHref}>
          Compare now <span aria-hidden="true">→</span>
        </Link>
      ) : (
        <span className="muted">Choose one more to compare</span>
      )}
    </aside>
  );
}

function money(value: string | null) {
  if (value === null) return "Not published";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function range(min: string | null, max: string | null) {
  if (min === null && max === null) return "Not published";
  if (min === max || max === null) return money(min);
  if (min === null) return money(max);
  return `${money(min)} – ${money(max)}`;
}

export function InlineComparePanel({
  procedureSlug,
  procedureName,
  items,
  payer,
  plan,
}: {
  procedureSlug: string;
  procedureName: string;
  items: ProcedureComparisonItem[];
  payer?: string;
  plan?: string;
}) {
  const selected = useChoices(procedureSlug);
  const selectedItems = selected
    .map((choice) =>
      items.find(
        (item) =>
          item.facility_id === choice.facilityId &&
          item.facility_location_id === choice.locationId,
      ),
    )
    .filter((item): item is ProcedureComparisonItem => Boolean(item));
  const query = new URLSearchParams({
    procedure: procedureSlug,
    items: selected.map((choice) => choice.key).join(","),
  });
  if (payer) query.set("payer", payer);
  if (plan) query.set("plan", plan);
  function clear() {
    sessionStorage.removeItem(storageKey(procedureSlug));
    window.dispatchEvent(new Event("carevero:selection"));
  }
  function remove(key: string) {
    const current = parseChoices(
      sessionStorage.getItem(storageKey(procedureSlug)) ?? "[]",
    );
    sessionStorage.setItem(
      storageKey(procedureSlug),
      JSON.stringify(current.filter((choice) => choice.key !== key)),
    );
    window.dispatchEvent(new Event("carevero:selection"));
  }
  return (
    <aside className="inline-compare" aria-live="polite">
      <div className="inline-compare-heading">
        <div>
          <span className="eyebrow">Side-by-side prices</span>
          <h2>Compare up to 3 hospitals</h2>
        </div>
        {selected.length > 0 && (
          <button className="text-button" type="button" onClick={clear}>
            Clear all
          </button>
        )}
      </div>
      {selectedItems.length === 0 ? (
        <div className="compare-empty">
          <span aria-hidden="true">⇄</span>
          <strong>Select hospitals to compare</strong>
          <p>
            Choose two or three results. Their real published prices will appear
            here.
          </p>
        </div>
      ) : (
        <div className="inline-compare-table-wrap">
          <table className="inline-compare-table">
            <caption className="sr-only">
              Selected hospital prices for {procedureName}
            </caption>
            <thead>
              <tr>
                <th scope="col">Price</th>
                {selectedItems.map((item) => (
                  <th scope="col" key={item.facility_location_id}>
                    <div className="compare-col-head">
                      <FacilityImage
                        name={item.facility_name}
                        variant="thumb"
                      />
                      <span className="compare-col-name">
                        {item.location_name ?? item.facility_name}
                        {item.location_name && (
                          <small>{item.facility_name}</small>
                        )}
                      </span>
                      <button
                        type="button"
                        className="compare-col-remove"
                        onClick={() =>
                          remove(
                            `${item.facility_id}~${item.facility_location_id}`,
                          )
                        }
                        aria-label={`Remove ${item.facility_name} from comparison`}
                      >
                        <span aria-hidden="true">×</span>
                      </button>
                    </div>
                  </th>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <th className="compare-placeholder" scope="col" key={index}>
                      Select hospital
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Cash price</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    <strong>
                      {range(item.cash_price_min, item.cash_price_max)}
                    </strong>
                  </td>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <td key={index}>—</td>
                  ),
                )}
              </tr>
              <tr>
                <th scope="row">
                  {payer ? "Matching published rates" : "Insurance rates"}
                </th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {payer
                      ? `${range(item.negotiated_price_min, item.negotiated_price_max)} · ${item.matching_negotiated_rate_count ?? 0} records`
                      : item.distinct_payer_count
                        ? `${item.distinct_payer_count} payer${item.distinct_payer_count === 1 ? "" : "s"} publish rates`
                        : "No normalized payer rates published"}
                  </td>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <td key={index}>—</td>
                  ),
                )}
              </tr>
              <tr>
                <th scope="row">Setting</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {item.service_settings.length
                      ? item.service_settings.join(", ").replaceAll("_", " ")
                      : "Not published"}
                  </td>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <td key={index}>—</td>
                  ),
                )}
              </tr>
              <tr>
                <th scope="row">CMS rating</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {item.cms_overall_rating
                      ? `${item.cms_overall_rating}/5 CMS`
                      : "Not available"}
                  </td>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <td key={index}>—</td>
                  ),
                )}
              </tr>
              <tr>
                <th scope="row">Distance</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {typeof item.distance_miles === "number"
                      ? `${item.distance_miles} mi`
                      : "—"}
                  </td>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <td key={index}>—</td>
                  ),
                )}
              </tr>
              <tr>
                <th scope="row">Published-price difference</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {item.is_lowest_comparable_cash
                      ? "Lowest shown"
                      : item.published_price_difference &&
                          Number(item.published_price_difference) > 0
                        ? `+${money(item.published_price_difference)}`
                        : "—"}
                  </td>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <td key={index}>—</td>
                  ),
                )}
              </tr>
            </tbody>
          </table>
        </div>
      )}
      <div className="inline-compare-footer">
        <span>{selected.length} of 3 selected</span>
        {selected.length >= 2 ? (
          <Link className="button" href={`/compare?${query}`}>
            View full comparison <span aria-hidden="true">→</span>
          </Link>
        ) : (
          <span className="muted">Select at least 2 hospitals</span>
        )}
      </div>
      {selected.length >= 2 && (
        <details className="save-comparison">
          <summary>Save comparison</summary>
          <p>
            Saving comparisons is coming soon — no account is needed to compare
            now.
          </p>
        </details>
      )}
      <p className="compare-disclaimer">
        Published prices are not a personalized estimate or guarantee of your
        final cost.
      </p>
    </aside>
  );
}
