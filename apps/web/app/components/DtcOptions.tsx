import Link from "next/link";
import type { DtcOptions as DtcOptionsData } from "../../lib/api";
import { localePath, type Locale, type Messages } from "../../lib/i18n";

function money(total: string): string {
  const n = Number(total);
  return Number.isFinite(n) ? `$${Math.round(n).toLocaleString()}` : total;
}

/**
 * Direct-to-consumer self-pay lab options — a SEPARATE, clearly-labelled surface
 * from the per-location published-price comparison. Every amount is a verified,
 * organization/product-level national DTC price (never a per-location price and
 * never a personalized estimate). Data comes from `/api/v1/procedures/{slug}/dtc-options`.
 */
export function DtcOptions({
  data,
  messages,
  locale,
}: {
  data: DtcOptionsData;
  messages: Messages;
  locale: Locale;
}) {
  if (!data.options.length) return null;
  const t = messages;
  return (
    <section className="dtc-section" aria-labelledby="dtc-heading">
      <div className="section-heading" style={{ marginBottom: "0.4rem" }}>
        <p className="eyebrow">{t.selfPay}</p>
        <h2 id="dtc-heading">{t.dtcHeading}</h2>
      </div>
      <p className="dtc-intro">{t.dtcIntro}</p>
      <ul className="dtc-list">
        {data.options.map((option) => (
          <li
            key={`${option.organization}-${option.product}`}
            className="dtc-card"
          >
            <div className="dtc-card-head">
              <span className="dtc-org">{option.organization}</span>
              <span className="dtc-total">
                <strong>{money(option.total)}</strong> {t.dtcTotalSuffix}
              </span>
            </div>
            <p className="dtc-product">{option.product}</p>
            <p className="dtc-components">{option.components}</p>
            {option.note ? <p className="dtc-note">{option.note}</p> : null}
            <div className="dtc-card-foot">
              <Link
                className="text-link"
                href={localePath(
                  locale,
                  `/providers?q=${encodeURIComponent(option.organization)}`,
                )}
              >
                {t.dtcFindLocations.replace("{org}", option.organization)}{" "}
                <span aria-hidden="true">→</span>
              </Link>
              <details className="dtc-source">
                <summary>{t.dtcSourceDetails}</summary>
                <div>
                  <p>{t.dtcVerified.replace("{date}", option.retrieved)}</p>
                  <p>{t.dtcNotLocationPrice}</p>
                  <a href={option.source_url} target="_blank" rel="noreferrer">
                    {option.source_url}
                  </a>
                </div>
              </details>
            </div>
          </li>
        ))}
      </ul>
      {data.disclaimer ? <p className="dtc-disclaimer">{data.disclaimer}</p> : null}
    </section>
  );
}
