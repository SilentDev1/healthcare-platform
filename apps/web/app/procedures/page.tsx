import Link from "next/link";
import { apiGet, Procedure } from "../../lib/api";

export default async function Procedures({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const category = (await searchParams).category;
  const suffix = category
    ? `?category=${encodeURIComponent(category)}&page_size=100`
    : "?page_size=100";
  try {
    const page = await apiGet<{ items: Procedure[] }>(
      `/api/v1/procedures${suffix}`,
    );
    return (
      <main>
        <p className="eyebrow">PROCEDURE CATALOG</p>
        <h1>Explore common services</h1>
        <p>Plain-language information only. Prices are coming later.</p>
        <div className="cards">
          {page.items.map((item) => (
            <article className="card" key={item.id}>
              <small>{item.category.name}</small>
              <h2>
                <Link href={`/procedures/${item.slug}`}>
                  {item.consumer_name}
                </Link>
              </h2>
              <p>{item.short_description}</p>
            </article>
          ))}
        </div>
      </main>
    );
  } catch {
    return (
      <main>
        <h1>Procedures</h1>
        <p className="error">Procedure data is unavailable.</p>
      </main>
    );
  }
}
