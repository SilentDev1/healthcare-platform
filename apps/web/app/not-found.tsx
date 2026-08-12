import Link from "next/link";
import { localePath } from "../lib/i18n";
import { requestLocale, requestMessages } from "../lib/i18n-server";

export default async function NotFound() {
  const locale = await requestLocale();
  const t = await requestMessages();
  return (
    <main className="narrow state-page">
      <p className="eyebrow">{t.nfPageNotFound}</p>
      <h1>{t.nfTitle}</h1>
      <p>{t.nfBody}</p>
      <div className="card-actions">
        <Link className="button" href={localePath(locale, "/search")}>
          {t.nfSearchCta}
        </Link>
        <Link className="button secondary" href={localePath(locale, "/hospitals")}>
          {t.nfBrowseHospitals}
        </Link>
        <Link
          className="button secondary"
          href={localePath(locale, "/procedures")}
        >
          {t.nfBrowseProcedures}
        </Link>
      </div>
    </main>
  );
}
