import Link from "next/link";
import type { Metadata } from "next";
import { apiGet, FacilityPage } from "../../lib/api";
import { launchRegion } from "../../lib/brand";
import { localePath } from "../../lib/i18n";
import { requestLocale, requestMessages } from "../../lib/i18n-server";

export const metadata: Metadata = {
  title: "Hospitals",
  description:
    "Browse active hospitals and service locations in Carevero’s New Hampshire launch region.",
  alternates: { canonical: "/hospitals" },
};

export default async function Facilities() {
  const locale = await requestLocale();
  const t = await requestMessages();
  try {
    const page = await apiGet<FacilityPage>(
      `/api/v1/facilities?state=${launchRegion.state}&page_size=100`,
    );
    return (
      <main>
        <nav className="breadcrumbs" aria-label={t.breadcrumb}>
          <Link href={localePath(locale, "/")}>{t.home}</Link>
          <span>/</span>
          <span>{t.hospitals}</span>
        </nav>
        <p className="eyebrow">{t.hospDirEyebrow}</p>
        <h1>{t.hospDirTitle}</h1>
        <p className="lede">{t.hospDirLede}</p>
        <div className="cards">
          {page.items.map((item) => (
            <article className="card" key={item.id}>
              <h2>
                <Link href={localePath(locale, `/hospitals/${item.id}`)}>
                  {item.display_name}
                </Link>
              </h2>
              <p>
                {item.locations[0]?.city}, {item.locations[0]?.state}
              </p>
              <span className="badge neutral">
                {item.facility_type ?? t.facilityTypeHospital}
              </span>
            </article>
          ))}
        </div>
      </main>
    );
  } catch {
    return (
      <main>
        <h1>{t.hospDirUnavailableTitle}</h1>
        <p className="error">{t.hospDirUnavailable}</p>
      </main>
    );
  }
}
