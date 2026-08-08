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
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{
    service_setting?: string;
    billing_class?: string;
    payer?: string;
  }>;
}) {
  const { slug } = await params;
  const filters = await searchParams;
  const queryParts = ["state=NH", "page_size=50"];
  if (filters.service_setting)
    queryParts.push(`setting=${encodeURIComponent(filters.service_setting)}`);
  if (filters.payer)
    queryParts.push(`payer=${encodeURIComponent(filters.payer)}`);
  try {
    const data = await apiGet<PricePage>(
      `/api/v1/procedures/${encodeURIComponent(slug)}/prices?${queryParts.join("&")}`,
    );

    const cashValues = data.items
      .map((i) => (i.cash_price_min ? Number(i.cash_price_min) : null))
      .filter((v): v is number => v !== null);
    const minCash = cashValues.length ? Math.min(...cashValues) : null;
    const maxCash = cashValues.length ? Math.max(...cashValues) : null;
    const avgCash = cashValues.length
      ? Math.round(cashValues.reduce((a, b) => a + b, 0) / cashValues.length)
      : null;
    const maxBar = maxCash ?? 1;

    return (
      <main>
        <Link href={`/procedures/${slug}`}>← Procedure details</Link>
        <h1>Published hospital prices</h1>
        <p>
          These values come from public hospital transparency files. They are
          not an exact patient cost or a complete episode price.
        </p>

        <form className="search-form" style={{ flexWrap: "wrap" }}>
          <select
            name="service_setting"
            defaultValue={filters.service_setting ?? ""}
            aria-label="Service setting"
            style={{
              padding: "0.6rem",
              border: "1px solid #9fb3ae",
              borderRadius: "0.5rem",
            }}
          >
            <option value="">All settings</option>
            <option value="inpatient">Inpatient</option>
            <option value="outpatient">Outpatient</option>
            <option value="emergency_department">Emergency</option>
          </select>
          <select
            name="billing_class"
            defaultValue={filters.billing_class ?? ""}
            aria-label="Billing class"
            style={{
              padding: "0.6rem",
              border: "1px solid #9fb3ae",
              borderRadius: "0.5rem",
            }}
          >
            <option value="">All billing classes</option>
            <option value="facility">Facility</option>
            <option value="professional">Professional</option>
          </select>
          <button>Filter</button>
        </form>

        {cashValues.length > 0 && (
          <section
            className="card"
            style={{ marginBottom: "1.5rem" }}
            aria-label="Statewide price summary"
          >
            <h2 style={{ margin: "0 0 0.5rem" }}>
              Statewide summary ({data.items.length} facilities)
            </h2>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: "1rem",
                textAlign: "center",
              }}
            >
              <div>
                <div style={{ color: "#526862", fontSize: "0.85rem" }}>
                  Lowest
                </div>
                <strong style={{ fontSize: "1.3rem" }}>
                  {money(String(minCash))}
                </strong>
              </div>
              <div>
                <div style={{ color: "#526862", fontSize: "0.85rem" }}>
                  Average
                </div>
                <strong style={{ fontSize: "1.3rem" }}>
                  {money(String(avgCash))}
                </strong>
              </div>
              <div>
                <div style={{ color: "#526862", fontSize: "0.85rem" }}>
                  Highest
                </div>
                <strong style={{ fontSize: "1.3rem" }}>
                  {money(String(maxCash))}
                </strong>
              </div>
            </div>
          </section>
        )}

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
                  <th style={{ width: "20%" }}>Range</th>
                  <th>Negotiated price</th>
                  <th>Setting</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => {
                  const cashMin = item.cash_price_min
                    ? Number(item.cash_price_min)
                    : 0;
                  const barWidth =
                    maxBar > 0
                      ? Math.max(2, Math.round((cashMin / maxBar) * 100))
                      : 0;
                  return (
                    <tr key={item.id}>
                      <td>
                        <Link href={`/facilities/${item.facility_id}`}>
                          {item.facility_name}
                        </Link>
                      </td>
                      <td>{item.city ?? "—"}</td>
                      <td>
                        {range(item.cash_price_min, item.cash_price_max)}
                      </td>
                      <td>
                        <div
                          style={{
                            background: "#e8efed",
                            borderRadius: "0.25rem",
                            height: "1rem",
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              background: "#087f5b",
                              width: `${barWidth}%`,
                              height: "100%",
                              borderRadius: "0.25rem",
                              transition: "width 0.3s",
                            }}
                          />
                        </div>
                      </td>
                      <td>
                        {range(
                          item.negotiated_price_min,
                          item.negotiated_price_max,
                        )}
                      </td>
                      <td>{item.service_setting}</td>
                      <td>
                        <a href={item.source_url}>Source</a> ·{" "}
                        {new Date(item.last_updated).toLocaleDateString(
                          "en-US",
                        )}
                      </td>
                    </tr>
                  );
                })}
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
