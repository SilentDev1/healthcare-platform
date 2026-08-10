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
        <nav className="breadcrumbs" aria-label="Breadcrumb">
          <Link href="/">Home</Link>
          <span>/</span>
          <span>Procedures</span>
        </nav>
        <p className="eyebrow">Care catalog</p>
        <h1>Explore common healthcare services</h1>
        <p className="lede">
          Plain-language guidance and published price comparisons—without
          requiring medical billing codes.
        </p>
        <div className="cards">
          {page.items.map((item) => (
            <article className="card" key={item.id}>
              <span className="badge neutral">{item.category.name}</span>
              <h2>
                <Link href={`/procedures/${item.slug}`}>
                  {item.consumer_name}
                </Link>
              </h2>
              <p>{item.short_description}</p>
              <Link
                className="button secondary"
                href={`/procedures/${item.slug}/prices`}
              >
                Compare prices
              </Link>
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
