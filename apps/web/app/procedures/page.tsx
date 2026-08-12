import Link from "next/link";
import type { Metadata } from "next";
import { apiGet, Procedure } from "../../lib/api";
import { localePath } from "../../lib/i18n";
import { requestLocale, requestMessages } from "../../lib/i18n-server";

export const metadata: Metadata = {
  title: "Procedures",
  description:
    "Browse plain-language healthcare procedures and compare available hospital-published prices.",
  alternates: { canonical: "/procedures" },
};

export default async function Procedures({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const locale = await requestLocale();
  const t = await requestMessages();
  const category = (await searchParams).category;
  const suffix = category
    ? `?category=${encodeURIComponent(category)}&page_size=100`
    : "?page_size=100";
  try {
    const page = await apiGet<{ items: Procedure[] }>(
      `/api/v1/procedures${suffix}`,
    );
    return (
      <main>
        <nav className="breadcrumbs" aria-label={t.breadcrumb}>
          <Link href={localePath(locale, "/")}>{t.home}</Link>
          <span>/</span>
          <span>{t.procedures}</span>
        </nav>
        <p className="eyebrow">{t.procDirEyebrow}</p>
        <h1>{t.procDirTitle}</h1>
        <p className="lede">{t.procDirLede}</p>
        <div className="cards">
          {page.items.map((item) => (
            <article className="card" key={item.id}>
              <span className="badge neutral">{item.category.name}</span>
              <h2>
                <Link href={localePath(locale, `/procedures/${item.slug}`)}>
                  {item.consumer_name}
                </Link>
              </h2>
              <p>{item.short_description}</p>
              <Link
                className="button secondary"
                href={localePath(locale, `/procedures/${item.slug}/prices`)}
              >
                {t.comparePrices}
              </Link>
            </article>
          ))}
        </div>
      </main>
    );
  } catch {
    return (
      <main>
        <h1>{t.procedures}</h1>
        <p className="error">{t.procDirUnavailable}</p>
      </main>
    );
  }
}
