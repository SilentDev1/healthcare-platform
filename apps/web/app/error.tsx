"use client";

import Link from "next/link";
import { localePath, messages } from "../lib/i18n";
import { useLocale } from "./components/useLocale";

export default function GlobalError({ reset }: { reset: () => void }) {
  const locale = useLocale();
  const t = messages[locale] ?? messages.en;
  return (
    <main className="narrow state-page">
      <p className="eyebrow">{t.errTemporaryProblem}</p>
      <h1>{t.errCouldntLoadPage}</h1>
      <p>{t.errNoPricesEstimated}</p>
      <div className="card-actions">
        <button className="button" type="button" onClick={reset}>
          {t.tryAgain}
        </button>
        <Link className="button secondary" href={localePath(locale, "/")}>
          {t.errReturnHome}
        </Link>
      </div>
    </main>
  );
}
