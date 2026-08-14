import Link from "next/link";
import type { ReactNode } from "react";
import { localePath, type Locale } from "../../lib/i18n";

export function ProcedureCard({
  id,
  slug,
  name,
  description,
  icon,
  locale,
  viewPricesLabel,
  query = "",
}: {
  id: string;
  slug: string;
  name: string;
  description?: string;
  icon?: ReactNode;
  locale: Locale;
  viewPricesLabel: string;
  query?: string;
}) {
  return (
    <article className="procdir-card" key={id}>
      {icon && (
        <span className="procdir-card-icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <div className="procdir-card-body">
        <h2 className="procdir-card-title">
          <Link href={localePath(locale, `/procedures/${slug}`)}>{name}</Link>
        </h2>
        {description && <p className="procdir-card-desc">{description}</p>}
        <Link
          className="procdir-card-cta"
          href={localePath(locale, `/procedures/${slug}/prices${query}`)}
        >
          {viewPricesLabel}
          <span aria-hidden="true"> →</span>
        </Link>
      </div>
    </article>
  );
}
