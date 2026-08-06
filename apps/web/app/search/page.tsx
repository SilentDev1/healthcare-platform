import Link from "next/link";
import { apiGet, SearchResult } from "../../lib/api";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const q = (await searchParams).q?.trim() ?? "";
  let items: SearchResult[] = [];
  let error = "";
  if (q.length >= 2) {
    try {
      items = (
        await apiGet<{ items: SearchResult[] }>(
          `/api/v1/search?q=${encodeURIComponent(q)}`,
        )
      ).items;
    } catch {
      error = "Search is temporarily unavailable.";
    }
  }
  return (
    <main>
      <p className="eyebrow">SEARCH</p>
      <h1>Find care and services</h1>
      <form className="search-form">
        <input
          name="q"
          defaultValue={q}
          minLength={2}
          maxLength={100}
          aria-label="Search"
          placeholder="Hospital, city, ZIP, or procedure"
        />
        <button>Search</button>
      </form>
      {error && <p className="error">{error}</p>}
      {q && !error && items.length === 0 && <p>No results found.</p>}
      <div className="cards">
        {items.map((item) => (
          <article
            className="card"
            key={`${item.entity_type}-${item.entity_id}`}
          >
            <small>{item.entity_type.replace("_", " ")}</small>
            <h2>
              <Link
                href={
                  item.entity_type === "facility"
                    ? `/facilities/${item.entity_id}`
                    : item.entity_type === "procedure"
                      ? `/procedures/${item.metadata.slug}`
                      : `/procedures?category=${item.metadata.slug}`
                }
              >
                {item.title}
              </Link>
            </h2>
            <p>{item.subtitle}</p>
            <p>{item.location}</p>
          </article>
        ))}
      </div>
    </main>
  );
}
