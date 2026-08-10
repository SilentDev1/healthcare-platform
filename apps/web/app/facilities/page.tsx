import Link from "next/link";
import type { Metadata } from "next";
import { apiGet, FacilityPage } from "../../lib/api";
import { launchRegion } from "../../lib/brand";

export const metadata: Metadata = {
  title: "Hospitals",
  description:
    "Browse active hospitals and service locations in Carevero’s New Hampshire launch region.",
  alternates: { canonical: "/hospitals" },
};

export default async function Facilities() {
  try {
    const page = await apiGet<FacilityPage>(
      `/api/v1/facilities?state=${launchRegion.state}&page_size=100`,
    );
    return (
      <main>
        <nav className="breadcrumbs">
          <Link href="/">Home</Link>
          <span>/</span>
          <span>Hospitals</span>
        </nav>
        <p className="eyebrow">Hospital directory</p>
        <h1>Explore hospitals</h1>
        <p className="lede">
          All active facilities remain visible, including those without
          currently publishable prices.
        </p>
        <div className="cards">
          {page.items.map((item) => (
            <article className="card" key={item.id}>
              <h2>
                <Link href={`/hospitals/${item.id}`}>{item.display_name}</Link>
              </h2>
              <p>
                {item.locations[0]?.city}, {item.locations[0]?.state}
              </p>
              <span className="badge neutral">
                {item.facility_type ?? "Hospital"}
              </span>
            </article>
          ))}
        </div>
      </main>
    );
  } catch {
    return (
      <main>
        <h1>Facilities</h1>
        <p className="error">Facility data is unavailable.</p>
      </main>
    );
  }
}
