import Link from "next/link";
import { apiGet, FacilityPage } from "../../lib/api";

export default async function Facilities() {
  try {
    const page = await apiGet<FacilityPage>(
      "/api/v1/facilities?state=NH&page_size=100",
    );
    return (
      <main>
        <p className="eyebrow">NEW HAMPSHIRE</p>
        <h1>Facility directory</h1>
        <div className="cards">
          {page.items.map((item) => (
            <article className="card" key={item.id}>
              <h2>
                <Link href={`/facilities/${item.id}`}>{item.display_name}</Link>
              </h2>
              <p>
                {item.locations[0]?.city}, {item.locations[0]?.state}
              </p>
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
