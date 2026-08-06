import { notFound } from "next/navigation";
import { apiGet, Procedure } from "../../../lib/api";

export default async function ProcedureDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let item: Procedure;
  try {
    item = await apiGet<Procedure>(
      `/api/v1/procedures/${encodeURIComponent(slug)}`,
    );
  } catch {
    notFound();
  }
  return (
    <main>
      <p className="eyebrow">{item.category.name}</p>
      <h1>{item.consumer_name}</h1>
      <p>{item.long_description}</p>
      <section className="card">
        <h2>What to know</h2>
        <p>Typical setting: {item.service_setting.replaceAll("_", " ")}</p>
        <p>Related terms: {item.aliases.join(", ")}</p>
        <p>{item.billing_notice}</p>
        <p>
          This is general information, not individualized medical advice. No
          price estimate is available yet.
        </p>
      </section>
    </main>
  );
}
