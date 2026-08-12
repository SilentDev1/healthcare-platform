"use client";

import Link from "next/link";
import { useMemo, useSyncExternalStore } from "react";
import type { ProcedureComparisonItem } from "../../lib/api";
import { messages, type Locale } from "../../lib/i18n";
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
  locale = "en",
}: {
  facilityId: string;
  locationId: string;
  name: string;
  procedureSlug: string;
  locale?: Locale;
}) {
  const t = messages[locale];
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
        aria-label={(active
          ? t.removeFromComparison
          : t.addToComparison
        ).replace("{name}", name)}
      >
        {active
          ? t.compareSelected
          : limitReached
            ? t.compareLimitReached
            : t.compareAdd}
      </button>
    </div>
  );
}

export function CompareTray({
  procedureSlug,
  payer,
  plan,
  locale = "en",
}: {
  procedureSlug: string;
  payer?: string;
  plan?: string;
  locale?: Locale;
}) {
  const t = messages[locale];
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
        <strong>
          {t.compareHospitals} ·{" "}
          {t.selectedOfThree.replace("{count}", String(selected.length))}
        </strong>
        <ul aria-label={t.selectedLocations}>
          {selected.map((choice) => (
            <li key={choice.key}>{choice.name}</li>
          ))}
        </ul>
      </div>
      <button className="text-button" type="button" onClick={clear}>
        {t.clear}
      </button>
      {selected.length >= 2 ? (
        <Link className="button" href={compareHref}>
          {t.compareNow} <span aria-hidden="true">→</span>
        </Link>
      ) : (
        <span className="muted">{t.chooseOneMore}</span>
      )}
    </aside>
  );
}

function money(value: string | null, notPublished = "Not published") {
  if (value === null) return notPublished;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function range(
  min: string | null,
  max: string | null,
  notPublished = "Not published",
) {
  if (min === null && max === null) return notPublished;
  if (min === max || max === null) return money(min, notPublished);
  if (min === null) return money(max, notPublished);
  return `${money(min, notPublished)} – ${money(max, notPublished)}`;
}

export function InlineComparePanel({
  procedureSlug,
  procedureName,
  items,
  payer,
  plan,
  locale = "en",
}: {
  procedureSlug: string;
  procedureName: string;
  items: ProcedureComparisonItem[];
  payer?: string;
  plan?: string;
  locale?: Locale;
}) {
  const t = messages[locale];
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
          <span className="eyebrow">{t.sideBySidePrices}</span>
          <h2>{t.compareUpToThree}</h2>
        </div>
        {selected.length > 0 && (
          <button className="text-button" type="button" onClick={clear}>
            {t.clearAll}
          </button>
        )}
      </div>
      {selectedItems.length === 0 ? (
        <div className="compare-empty">
          <span aria-hidden="true">⇄</span>
          <strong>{t.selectHospitalsToCompare}</strong>
          <p>{t.chooseTwoOrThree}</p>
        </div>
      ) : (
        <div className="inline-compare-table-wrap">
          <table className="inline-compare-table">
            <caption className="sr-only">
              {t.selectedHospitalPricesCaption.replace(
                "{procedure}",
                procedureName,
              )}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t.price}</th>
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
                        aria-label={t.removeFromComparison.replace(
                          "{name}",
                          item.facility_name,
                        )}
                      >
                        <span aria-hidden="true">×</span>
                      </button>
                    </div>
                  </th>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <th className="compare-placeholder" scope="col" key={index}>
                      {t.selectHospital}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">{t.cashPrice}</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    <strong>
                      {range(
                        item.cash_price_min,
                        item.cash_price_max,
                        t.notPublished,
                      )}
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
                  {payer ? t.matchingPublishedRates : t.insuranceRates}
                </th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {payer
                      ? `${range(item.negotiated_price_min, item.negotiated_price_max, t.notPublished)} · ${t.recordsCount.replace("{count}", String(item.matching_negotiated_rate_count ?? 0))}`
                      : item.distinct_payer_count
                        ? item.distinct_payer_count === 1
                          ? t.oneCompanyPublishesRates
                          : `${item.distinct_payer_count} ${t.companiesPublishRates}`
                        : t.noInsurancePrices}
                  </td>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <td key={index}>—</td>
                  ),
                )}
              </tr>
              <tr>
                <th scope="row">{t.setting}</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {item.service_settings.length
                      ? item.service_settings.join(", ").replaceAll("_", " ")
                      : t.notPublished}
                  </td>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <td key={index}>—</td>
                  ),
                )}
              </tr>
              <tr>
                <th scope="row">{t.cmsRating}</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {item.cms_overall_rating
                      ? t.cmsRatingValue.replace(
                          "{rating}",
                          String(item.cms_overall_rating),
                        )
                      : t.notAvailable}
                  </td>
                ))}
                {Array.from({ length: 3 - selectedItems.length }).map(
                  (_, index) => (
                    <td key={index}>—</td>
                  ),
                )}
              </tr>
              <tr>
                <th scope="row">{t.distance}</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {typeof item.distance_miles === "number"
                      ? `${item.distance_miles} ${t.milesUnit}`
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
                <th scope="row">{t.priceDifference}</th>
                {selectedItems.map((item) => (
                  <td key={item.facility_location_id}>
                    {item.is_lowest_comparable_cash
                      ? t.lowestShown
                      : item.published_price_difference &&
                          Number(item.published_price_difference) > 0
                        ? `+${money(item.published_price_difference, t.notPublished)}`
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
        <span>
          {t.selectedOfThree.replace("{count}", String(selected.length))}
        </span>
        {selected.length >= 2 ? (
          <Link className="button" href={`/compare?${query}`}>
            {t.viewFullComparison} <span aria-hidden="true">→</span>
          </Link>
        ) : (
          <span className="muted">{t.selectAtLeastTwo}</span>
        )}
      </div>
      {selected.length >= 2 && (
        <details className="save-comparison">
          <summary>{t.saveComparison}</summary>
          <p>{t.saveComparisonNote}</p>
        </details>
      )}
      <p className="compare-disclaimer">{t.compareDisclaimer}</p>
    </aside>
  );
}
