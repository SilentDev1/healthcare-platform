import { notFound } from "next/navigation";
import type { Metadata } from "next";
import Link from "next/link";
import { apiGet, Procedure } from "../../../lib/api";
import { PricingDisclaimer, SourceAttribution } from "../../components/ui";
import {
  ProcedureResults,
  type ProcedureResultsFilters,
} from "../../components/ProcedureResults";
import { launchRegion } from "../../../lib/brand";
import { localePath, type Messages } from "../../../lib/i18n";
import { requestLocale, requestMessages } from "../../../lib/i18n-server";

const CATEGORY_I18N_KEYS: Record<string, keyof Messages> = {
  imaging: "procCat_imaging",
  laboratory: "procCat_laboratory",
  preventive: "procCat_preventive",
  emergency: "procCat_emergency",
  maternity: "procCat_maternity",
  outpatient_surgery: "procCat_outpatient_surgery",
  inpatient_surgery: "procCat_inpatient_surgery",
  cardiology: "procCat_cardiology",
  orthopedics: "procCat_orthopedics",
  gastroenterology: "procCat_gastroenterology",
  ophthalmology: "procCat_ophthalmology",
  rehabilitation: "procCat_rehabilitation",
  other: "procCat_other",
};

function consumerCategoryName(t: Messages, slug: string): string {
  const key = CATEGORY_I18N_KEYS[slug];
  if (key) return t[key] as string;
  return slug.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const item = await apiGet<Procedure>(
      `/api/v1/procedures/${encodeURIComponent(slug)}`,
    );
    return {
      title: `${item.consumer_name} prices`,
      description: `Compare hospital-published prices for ${item.consumer_name.toLowerCase()} in ${launchRegion.name}.`,
      alternates: { canonical: `/procedures/${item.slug}` },
    };
  } catch {
    return { title: "Procedure information" };
  }
}

export default async function ProcedureDetail({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<ProcedureResultsFilters>;
}) {
  const { slug } = await params;
  const filters = await searchParams;
  const locale = await requestLocale();
  const t = await requestMessages();
  let item: Procedure;
  try {
    item = await apiGet<Procedure>(
      `/api/v1/procedures/${encodeURIComponent(slug)}`,
    );
  } catch {
    notFound();
  }
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "MedicalProcedure",
    name: item.consumer_name,
    description: item.short_description,
  };
  return (
    <main>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
      <nav className="breadcrumbs" aria-label={t.breadcrumb}>
        <Link href={localePath(locale, "/")}>{t.home}</Link>
        <span>/</span>
        <Link href={localePath(locale, "/procedures")}>{t.procedures}</Link>
        <span>/</span>
        <span>{item.consumer_name}</span>
      </nav>
      <div className="page-heading">
        <p className="eyebrow">{consumerCategoryName(t, item.category.slug)}</p>
        <h1>{item.consumer_name}</h1>
        <p className="lede">{item.long_description}</p>
      </div>
      <div className="feature-grid procedure-facts">
        <section className="card">
          <h2>{t.procTypicalSetting}</h2>
          <p>
            {item.service_setting
              .replace(/[-_]/g, " ")
              .replace(/\b\w/g, (c) => c.toUpperCase())}
          </p>
        </section>
        <section className="card">
          <h2>{t.procWhatIncluded}</h2>
          <p>
            {item.billing_notice ===
            "Final treatment and billing may involve multiple services."
              ? t.procBillingNoticeDefault
              : item.billing_notice}
          </p>
        </section>
        <section className="card">
          <h2>{t.procWhatSeparate}</h2>
          <p>{t.procWhatSeparateBody}</p>
        </section>
      </div>

      {/* The actual hospital-shopping experience comes BEFORE the educational
          sections: who published a price, where they are, how much, compare. */}
      <ProcedureResults
        slug={slug}
        procedureName={item.consumer_name}
        filters={filters}
        locale={locale}
        messages={t}
        basePath={`/procedures/${slug}`}
      />

      <section className="card">
        <h2>{t.procQualityConsiderations}</h2>
        <p>{t.procQualityConsiderationsBody}</p>
        <p>
          {t.procRelatedTerms} {item.aliases.join(", ") || t.procNoneListed}
        </p>
      </section>
      <section className="section" style={{ paddingInline: 0 }}>
        <div className="section-heading">
          <h2>{t.sourcesHeading}</h2>
        </div>
        {/* Pricing data and quality data come from different sources — never
            imply CMS Care Compare is the source of hospital prices. */}
        <SourceAttribution messages={t} />
        <SourceAttribution quality messages={t} />
      </section>
      <PricingDisclaimer messages={t} />
      <p className="muted">{t.procEducationalNote}</p>
    </main>
  );
}
