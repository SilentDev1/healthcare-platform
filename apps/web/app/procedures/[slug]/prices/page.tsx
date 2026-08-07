import Link from "next/link";
import { apiGet, type PricePage } from "../../../../lib/api";

const money = (value: string | null) =>
  value === null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
      }).format(Number(value));
const range = (low: string | null, high: string | null) =>
  low === high ? money(low) : `${money(low)} – ${money(high)}`;

export default async function ProcedurePrices({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  try {
    const data = await apiGet<PricePage>(
      `/api/v1/procedures/${encodeURIComponent(slug)}/prices?state=NH&page_size=50`,
    );
    return (
      <main>
        <Link href={`/procedures/${slug}`}>← Procedure details</Link>
        <h1>Published hospital prices</h1>
        <p>
          These values come from public hospital transparency files. They are
          not an exact patient cost or a complete episode price.
        </p>
        {data.items.length === 0 ? (
          <p>
            No reviewed, publishable prices are available for this procedure.
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Facility</th>
                  <th>City</th>
                  <th>Cash price</th>
                  <th>Negotiated price</th>
                  <th>Setting</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link href={`/facilities/${item.facility_id}`}>
                        {item.facility_name}
                      </Link>
                    </td>
                    <td>{item.city ?? "—"}</td>
                    <td>{range(item.cash_price_min, item.cash_price_max)}</td>
                    <td>
                      {range(
                        item.negotiated_price_min,
                        item.negotiated_price_max,
                      )}
                    </td>
                    <td>{item.service_setting}</td>
                    <td>
                      <a href={item.source_url}>Source</a> ·{" "}
                      {new Date(item.last_updated).toLocaleDateString("en-US")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <section className="card">
          <h2>Important limitations</h2>
          <p>
            Physician, anesthesia, imaging, pathology, laboratory, medication,
            implant, or other charges may be separate. A published negotiated
            rate does not prove current network participation. Actual
            out-of-pocket cost depends on benefits, deductible, coinsurance,
            copays, authorization, and services received.
          </p>
        </section>
      </main>
    );
  } catch (error) {
    return (
      <main>
        <h1>Published hospital prices</h1>
        <p className="error" role="alert">
          Unable to load prices:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}
