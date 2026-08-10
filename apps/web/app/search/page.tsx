"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CareSearch } from "../components/CareSearch";
import { EmptyState, ErrorState, LoadingSkeleton } from "../components/ui";
import type { SearchResult } from "../../lib/api";
const API_URL =
  process.env.NEXT_PUBLIC_CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

function SearchContent() {
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const location = params.get("location") ?? "";
  const payer = params.get("payer") ?? "";
  const [items, setItems] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(Boolean(q));
  const [error, setError] = useState(false);
  useEffect(() => {
    if (q.length < 2) return;
    const controller = new AbortController();
    const reset = setTimeout(() => {
      setLoading(true);
      setError(false);
    }, 0);
    const query = new URLSearchParams({ q });
    if (/^\d{5}$/.test(location)) query.set("postal_code", location);
    fetch(`${API_URL}/api/v1/search?${query}`, { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((d) => setItems(d.items ?? []))
      .catch((e) => {
        if (e.name !== "AbortError") setError(true);
      })
      .finally(() => setLoading(false));
    return () => {
      clearTimeout(reset);
      controller.abort();
    };
  }, [q, location]);
  return (
    <main>
      <div className="page-heading">
        <p className="eyebrow">Find care</p>
        <h1>{q ? `Results for “${q}”` : "What care do you need?"}</h1>
        <p className="lede">
          Search procedures, hospitals, cities, or ZIP codes using everyday
          language.
        </p>
      </div>
      <CareSearch
        compact
        initialCare={q}
        initialLocation={location}
        initialPayer={payer}
      />
      {q && (
        <div className="toolbar">
          <strong>
            {loading
              ? "Searching…"
              : `${items.length} matching result${items.length === 1 ? "" : "s"}`}
          </strong>
          <span className="muted">
            Only verified catalog and facility records
          </span>
        </div>
      )}
      {loading ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorState retryHref={`/search?q=${encodeURIComponent(q)}`} />
      ) : q && items.length === 0 ? (
        <EmptyState title="No matching care or hospital found">
          Try a broader term, a nearby city, or browse the procedure catalog. A
          missing result does not mean the service is unavailable.
        </EmptyState>
      ) : (
        <div className="cards">
          {items.map((item) => (
            <article
              className="card"
              key={`${item.entity_type}-${item.entity_id}`}
            >
              <span className="badge neutral">
                {item.entity_type.replaceAll("_", " ")}
              </span>
              <h2>{item.title}</h2>
              <p>{item.subtitle}</p>
              {item.location && <p className="location">{item.location}</p>}
              <Link
                className="button"
                href={
                  item.entity_type === "facility"
                    ? `/hospitals/${item.entity_id}`
                    : item.entity_type === "procedure"
                      ? `/procedures/${item.metadata.slug}/prices?location=${encodeURIComponent(location)}${payer ? `&payer=${encodeURIComponent(payer)}` : ""}`
                      : `/procedures?category=${item.metadata.slug}`
                }
              >
                {item.entity_type === "procedure"
                  ? "Compare published prices"
                  : "View details"}
              </Link>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <main>
          <LoadingSkeleton />
        </main>
      }
    >
      <SearchContent />
    </Suspense>
  );
}
