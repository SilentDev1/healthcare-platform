import { apiGet, SearchResult } from "../../lib/api";
export default async function Search({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const q = (await searchParams).q ?? "";
  let items: SearchResult[] = [];
  let error = "";
  if (q.length >= 2)
    try {
      items = (
        await apiGet<Page<SearchResult>>(
          `/api/v1/search?q=${encodeURIComponent(q)}`,
        )
      ).items;
    } catch {
      error = "Search API unavailable.";
    }
  return (
    <main>
      <p className="eyebrow">INTERNAL ONLY</p>
      <h1>Search testing</h1>
      <form className="panel">
        <label>
          Query <input name="q" defaultValue={q} minLength={2} />
        </label>{" "}
        <button>Run</button>
      </form>
      {error && <p className="error">{error}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Result</th>
              <th>Type</th>
              <th>Score</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.entity_id}>
                <td>
                  {i.title}
                  <br />
                  <small>{i.subtitle}</small>
                </td>
                <td>{i.entity_type}</td>
                <td>{i.score}</td>
                <td>{i.match_reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {q && !error && items.length === 0 && <p>No results.</p>}
    </main>
  );
}
interface Page<T> {
  items: T[];
}
