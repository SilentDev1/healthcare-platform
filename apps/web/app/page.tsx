import Link from "next/link";
import { apiGet, type FacilityPage } from "../lib/api";

export default async function Home() {
  try {
    const data = await apiGet<FacilityPage>(
      "/api/v1/facilities?state=NH&page_size=100",
    );
    return (
      <main>
        <p className="eyebrow">NEW HAMPSHIRE HEALTHCARE</p>
        <h1>Find a New Hampshire hospital.</h1>
        <p>
          Explore official CMS facility and quality information. Pricing
          comparison is coming later.
        </p>
        <h2>{data.total} facilities</h2>
        {data.items.length === 0 ? (
          <p>No facilities are currently available.</p>
        ) : (
          <ul className="directory">
            {data.items.map((facility) => (
              <li key={facility.id}>
                <Link href={`/facilities/${facility.id}`}>
                  {facility.display_name}
                </Link>
                <span>
                  {facility.locations[0]?.city ?? "New Hampshire"} ·{" "}
                  {facility.facility_type ?? "Hospital"}
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="source">
          Source: Centers for Medicare &amp; Medicaid Services (CMS).
        </p>
      </main>
    );
  } catch (error) {
    return (
      <main>
        <h1>New Hampshire facilities</h1>
        <p className="error" role="alert">
          Unable to load the facility directory:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}
