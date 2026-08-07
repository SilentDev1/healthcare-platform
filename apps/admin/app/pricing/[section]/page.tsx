import Link from "next/link";
import { apiGet, type Page, type PricingAdminItem } from "../../../lib/api";

const allowed = new Set([
  "sources",
  "source-discovery-runs",
  "source-discovery-observations",
  "import-runs",
  "records",
  "rates",
  "unmatched",
  "anomalies",
  "procedure-candidates",
  "payers",
  "plans",
  "facility-procedure-summaries",
]);

export default async function PricingQueue({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (!allowed.has(section))
    return (
      <main>
        <h1>Unknown pricing queue</h1>
      </main>
    );
  try {
    const data = await apiGet<Page<PricingAdminItem>>(
      `/api/v1/admin/pricing/${section}?page_size=25`,
    );
    return (
      <main>
        <Link href="/pricing">← Pricing dashboard</Link>
        <p className="eyebrow">INTERNAL ONLY</p>
        <h1>{section.replaceAll("-", " ")}</h1>
        <p>{data.total} records</p>
        {data.items.length === 0 ? (
          <p>No records require display.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>
                      <pre>{JSON.stringify(item.data, null, 2)}</pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    );
  } catch (error) {
    return (
      <main>
        <h1>{section.replaceAll("-", " ")}</h1>
        <p className="error" role="alert">
          Unable to load queue:{" "}
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
      </main>
    );
  }
}
