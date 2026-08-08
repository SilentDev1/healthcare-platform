"use client";

import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { SearchResult, SearchSuggestion } from "../../lib/api";

const API_URL =
  process.env.NEXT_PUBLIC_CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

export default function SearchPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";
  const [query, setQuery] = useState(initialQ);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const inputRef = useRef<HTMLInputElement>(null);

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([]);
      setSearched(false);
      return;
    }
    try {
      const res = await fetch(
        `${API_URL}/api/v1/search?q=${encodeURIComponent(q)}`,
      );
      if (!res.ok) throw new Error("failed");
      const data = await res.json();
      setResults(data.items ?? []);
      setError("");
      setSearched(true);
    } catch {
      setError("Search is temporarily unavailable.");
      setSearched(true);
    }
  }, []);

  // Run search on initial load if q is set
  useEffect(() => {
    if (initialQ.length >= 2) doSearch(initialQ);
  }, [initialQ, doSearch]);

  // Debounced suggestions
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.length < 2) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `${API_URL}/api/v1/search/suggestions?q=${encodeURIComponent(query)}&limit=6`,
        );
        if (res.ok) {
          const items: SearchSuggestion[] = await res.json();
          setSuggestions(items);
          setShowSuggestions(true);
        }
      } catch {
        // silently fail suggestions
      }
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setShowSuggestions(false);
    router.push(`/search?q=${encodeURIComponent(query)}`);
    doSearch(query);
  }

  function handleSuggestionClick(item: SearchSuggestion) {
    setShowSuggestions(false);
    setQuery(item.title);
    router.push(`/search?q=${encodeURIComponent(item.title)}`);
    doSearch(item.title);
  }

  return (
    <main>
      <p className="eyebrow">SEARCH</p>
      <h1>Find care and services</h1>
      <form className="search-form" onSubmit={handleSubmit}>
        <div style={{ flex: 1, position: "relative" }}>
          <input
            ref={inputRef}
            name="q"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            minLength={2}
            maxLength={100}
            aria-label="Search"
            placeholder="Hospital, city, ZIP, or procedure"
            autoComplete="off"
            style={{ width: "100%", boxSizing: "border-box" }}
          />
          {showSuggestions && suggestions.length > 0 && (
            <ul
              style={{
                position: "absolute",
                top: "100%",
                left: 0,
                right: 0,
                background: "white",
                border: "1px solid #d7e1de",
                borderRadius: "0 0 0.5rem 0.5rem",
                listStyle: "none",
                padding: 0,
                margin: 0,
                zIndex: 10,
                boxShadow: "0 4px 6px rgba(0,0,0,0.1)",
              }}
            >
              {suggestions.map((item) => (
                <li
                  key={`${item.entity_type}-${item.entity_id}`}
                  onMouseDown={() => handleSuggestionClick(item)}
                  style={{
                    padding: "0.6rem 0.9rem",
                    cursor: "pointer",
                    borderBottom: "1px solid #f0f0f0",
                    fontSize: "0.95rem",
                  }}
                >
                  <small
                    style={{
                      color: "#526862",
                      fontSize: "0.75rem",
                      textTransform: "uppercase",
                    }}
                  >
                    {item.entity_type.replace("_", " ")}
                  </small>
                  <div style={{ fontWeight: 600, color: "#087f5b" }}>
                    {item.title}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button>Search</button>
      </form>
      {error && <p className="error">{error}</p>}
      {searched && !error && results.length === 0 && <p>No results found.</p>}
      <div className="cards">
        {results.map((item) => (
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
