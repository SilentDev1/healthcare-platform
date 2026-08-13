import type { Metadata } from "next";
import { apiGet, Procedure, ProcedureCategory } from "../../lib/api";
import { requestLocale, requestMessages } from "../../lib/i18n-server";
import { ProceduresDirectory } from "./ProceduresDirectory";

export const metadata: Metadata = {
  title: "Procedures",
  description:
    "Browse plain-language healthcare procedures and compare available hospital-published prices.",
  alternates: { canonical: "/procedures" },
};

export default async function Procedures({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; q?: string; sort?: string }>;
}) {
  const locale = await requestLocale();
  const t = await requestMessages();
  const params = await searchParams;

  try {
    const [procedurePage, categories] = await Promise.all([
      apiGet<{ items: Procedure[] }>("/api/v1/procedures?page_size=100"),
      apiGet<{ items: ProcedureCategory[] }>(
        "/api/v1/procedure-categories?page_size=100",
      ).catch(() => ({ items: [] as ProcedureCategory[] })),
    ]);

    return (
      <ProceduresDirectory
        procedures={procedurePage.items}
        categories={categories.items}
        locale={locale}
        messages={t}
        initialCategory={params.category}
        initialQuery={params.q}
        initialSort={params.sort}
      />
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
