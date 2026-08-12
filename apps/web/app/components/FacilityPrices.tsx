"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { FacilityProcedureOverviewItem } from "../../lib/api";
import { localePath, messages as allMessages, type Locale, type Messages } from "../../lib/i18n";
import { PriceRange, SourceAttribution } from "./ui";

export function FacilityPrices({
  items,
  messages,
  locale = "en",
}: {
  items: FacilityProcedureOverviewItem[];
  messages?: Messages;
  locale?: Locale;
}) {
  const t = messages ?? allMessages[locale] ?? allMessages.en;
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
        <label htmlFor="facility-price-search">{t.fpSearchProcedures}</label>
        <input
          id="facility-price-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t.fpSearchPlaceholder}
        />
        <span className="field-help" role="status">
          {(filtered.length === 1
            ? t.fpResultCountOne
            : t.fpResultCountOther
          ).replace("{count}", String(filtered.length))}
        </span>
      </div>
      {filtered.length ? (
        <div className="table-wrap">
          <table className="price-table">
            <thead>
              <tr>
                <th scope="col">{t.fpProcedureAndLocation}</th>
                <th scope="col">{t.cashPrice}</th>
                <th scope="col">{t.fpInsurancePricing}</th>
                <th scope="col">{t.setting}</th>
                <th scope="col">{t.fpSource}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((price) => (
                <tr
                  key={`${price.procedure_slug}-${price.facility_location_id}`}
                >
                  <td data-label={t.fpProcedureAndLocation}>
                    <Link
                      href={localePath(
                        locale,
                        `/procedures/${price.procedure_slug}/prices`,
                      )}
                    >
                      {price.procedure_name}
                    </Link>
                    <small>
                      {price.location_name ??
                        price.city ??
                        t.fpLocationNotLabeled}
                    </small>
                  </td>
                  <td data-label={t.cashPrice}>
                    <PriceRange
                      min={price.cash_price_min}
                      max={price.cash_price_max}
                      messages={t}
                    />
                  </td>
                  <td data-label={t.fpInsurancePricing}>
                    {price.negotiated_price_min !== null ? (
                      <Link
                        href={localePath(
                          locale,
                          `/procedures/${price.procedure_slug}/prices`,
                        )}
                      >
                        {t.fpRatesAvailableChoosePayer}
                      </Link>
                    ) : (
                      t.fpNoNormalizedRates
                    )}
                  </td>
                  <td data-label={t.setting}>
                    {price.service_settings.join(", ").replaceAll("_", " ")}
                  </td>
                  <td data-label={t.fpSource}>
                    <SourceAttribution
                      updated={price.latest_updated}
                      url={price.source_url}
                      showLink={false}
                      messages={t}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="inline-empty">{t.fpNoProceduresMatch}</p>
      )}
    </>
  );
}
