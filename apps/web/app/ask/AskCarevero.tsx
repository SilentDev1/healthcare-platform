"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FacilityImage } from "../components/FacilityImage";
import { askMessages } from "../../lib/ask-i18n";
import { localePath, type Locale } from "../../lib/i18n";

// Same-origin Next.js proxy routes (server-side reach the API). This keeps every
// request first-party: no CORS, works on any web origin and in any browser, and
// never exposes the API URL to the client.

/** Minimal shapes we consume (grounded results come from the deterministic search/price API). */
interface ResolveResponse {
  domain: string;
  intent_type: string;
  candidate_slugs: string[];
  clarification_needed: boolean;
  clarification_question: string | null;
  refusal_message: string | null;
  used_llm: boolean;
}
interface SearchItem {
  entity_type: string;
  entity_id: string;
  title: string;
  subtitle: string;
  location: string | null;
  metadata: {
    slug?: string;
    capability?: string;
    location_type?: string;
    organization_name?: string | null;
    image_url?: string | null;
    image_alt?: string | null;
    image_attribution?: string | null;
  };
}
interface PriceRow {
  facility_id: string;
  facility_name: string;
  city: string | null;
  cash_price_min: number | null;
  negotiated_price_min: number | null;
}

type Turn =
  | { role: "user"; text: string }
  | {
      role: "assistant";
      kind: "message" | "medical" | "out_of_scope" | "results" | "error" | "empty";
      text?: string;
      followup?: string;
      service?: string;
      locationLabel?: string;
      procedures?: SearchItem[];
      locations?: SearchItem[];
      prices?: { slug: string; rows: PriceRow[] };
    };

function money(n: number | null): string | null {
  if (n === null || n === undefined) return null;
  return `$${Math.round(n).toLocaleString()}`;
}

export function AskCarevero({ locale }: { locale: Locale }) {
  const t = askMessages[locale] ?? askMessages.en;
  const params = useSearchParams();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const liveRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, busy]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setInput("");
    setTurns((prev) => [...prev, { role: "user", text: q }]);
    setBusy(true);
    try {
      // 1) Medical / out-of-scope gate + canonical intent (server-side, deterministic-first).
      let resolve: ResolveResponse | null = null;
      try {
        const r = await fetch(`/api/ask/resolve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: q, locale }),
        });
        if (r.ok) resolve = (await r.json()) as ResolveResponse;
      } catch {
        resolve = null; // fall through to deterministic search (fallback state)
      }

      if (resolve?.domain === "medical_advice") {
        setTurns((prev) => [
          ...prev,
          { role: "assistant", kind: "medical", text: resolve?.refusal_message || t.medicalBoundary, followup: t.medicalFollowup },
        ]);
        return;
      }
      if (resolve?.domain === "out_of_scope") {
        setTurns((prev) => [...prev, { role: "assistant", kind: "out_of_scope", text: resolve?.refusal_message || t.outOfScope }]);
        return;
      }

      // 2) Grounded results from the DETERMINISTIC search API (prices never come from the model).
      const search = await fetch(
        `/api/ask/search?q=${encodeURIComponent(q)}&locale=${encodeURIComponent(locale)}`,
      ).then((r) => (r.ok ? r.json() : { items: [], capability_locations: [] }));
      const items: SearchItem[] = search.items ?? [];
      const locations: SearchItem[] = search.capability_locations ?? [];
      const procedures = items.filter((i) => i.entity_type === "procedure" && i.metadata.slug);

      // If a single procedure is clearly identified, fetch a few REAL price rows to show inline.
      let prices: { slug: string; rows: PriceRow[] } | undefined;
      const slug = procedures[0]?.metadata.slug || resolve?.candidate_slugs?.[0];
      if (slug && procedures.length <= 2 && !slug.match(/^(laboratory|imaging|urgent_care|hospital|ambulatory_surgery|physical_therapy|rehabilitation|chiropractic|emergency_department|freestanding_emergency_department)$/)) {
        try {
          const p = await fetch(
            `/api/ask/prices?slug=${encodeURIComponent(slug)}&state=NH&page_size=4`,
          ).then((r) => (r.ok ? r.json() : { items: [] }));
          if (p.items?.length) prices = { slug, rows: p.items.slice(0, 4) };
        } catch {
          /* price fetch optional */
        }
      }

      if (!procedures.length && !locations.length && !prices) {
        setTurns((prev) => [...prev, { role: "assistant", kind: "empty", text: t.noResults }]);
        return;
      }
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          kind: "results",
          text: resolve ? undefined : t.fallback,
          service: procedures[0]?.title,
          locationLabel: locations[0]?.location || undefined,
          procedures: procedures.slice(0, 4),
          locations: locations.slice(0, 6),
          prices,
        },
      ]);
    } catch {
      setTurns((prev) => [...prev, { role: "assistant", kind: "error", text: t.error }]);
    } finally {
      setBusy(false);
    }
  }

  // Deep-link: /ask?q=... (from the homepage entry / contextual entry points).
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const q = params.get("q");
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (q) void ask(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="ask-shell">
      <p className="ask-safety" role="note">
        {t.safety}
      </p>

      <div className="ask-convo" aria-live="polite" ref={liveRef}>
        {turns.length === 0 ? (
          <div className="ask-starters">
            {t.starters.map((s) => (
              <button key={s} type="button" className="ask-chip" onClick={() => void ask(s)}>
                {s}
              </button>
            ))}
          </div>
        ) : null}

        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <div key={i} className="ask-turn ask-user">
              <span className="ask-role">{t.you}</span>
              <p>{turn.text}</p>
            </div>
          ) : (
            <div key={i} className={`ask-turn ask-assistant ask-${turn.kind}`}>
              <span className="ask-role">{t.assistant}</span>
              {turn.text ? <p>{turn.text}</p> : null}
              {turn.kind === "medical" && turn.followup ? (
                <p className="ask-followup">{turn.followup}</p>
              ) : null}

              {turn.kind === "results" ? (
                <div className="ask-results">
                  {turn.service ? (
                    <p className="ask-label">
                      <strong>{t.labelService}:</strong> {turn.service}
                      {turn.locationLabel ? (
                        <>
                          {" · "}
                          <strong>{t.labelLocation}:</strong> {turn.locationLabel}
                        </>
                      ) : null}
                    </p>
                  ) : null}

                  {turn.prices?.rows?.length ? (
                    <>
                      <p className="ask-label">{t.labelPrices}</p>
                      <ul className="ask-cards">
                        {turn.prices.rows.map((row) => {
                          const price = money(row.cash_price_min ?? row.negotiated_price_min);
                          return (
                            <li key={row.facility_id + (row.city ?? "")} className="ask-card">
                              <span className="ask-card-name">{row.facility_name}</span>
                              <span className="ask-card-meta">{row.city}</span>
                              <span className="ask-card-price">
                                {price ?? t.priceNotAvailable}
                              </span>
                              <Link
                                className="ask-card-link"
                                href={localePath(locale, `/hospitals/${row.facility_id}`)}
                              >
                                {t.viewDetails}
                              </Link>
                            </li>
                          );
                        })}
                      </ul>
                      <Link
                        className="ask-more"
                        href={localePath(locale, `/procedures/${turn.prices.slug}/prices?state=NH`)}
                      >
                        {t.labelResults} →
                      </Link>
                    </>
                  ) : null}

                  {turn.locations?.length ? (
                    <>
                      <p className="ask-label">{t.labelResults}</p>
                      <ul className="ask-cards">
                        {turn.locations.map((loc) => (
                          <li key={loc.entity_id} className="ask-card ask-card-loc">
                            <FacilityImage
                              name={loc.title}
                              imageUrl={loc.metadata.image_url}
                              imageAlt={loc.metadata.image_alt}
                              attribution={loc.metadata.image_attribution}
                              placeholderLabel={null}
                              variant="thumb"
                            />
                            <span className="ask-card-body">
                              <span className="ask-card-name">{loc.title}</span>
                              <span className="ask-card-meta">{loc.subtitle}</span>
                              <span className="ask-card-price">{t.priceNotAvailable}</span>
                            </span>
                            <Link
                              className="ask-card-link"
                              href={localePath(locale, `/hospitals/${loc.entity_id}`)}
                            >
                              {t.viewLocation}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : null}

                  {turn.procedures?.length && !turn.prices ? (
                    <ul className="ask-cards">
                      {turn.procedures.map((p) => (
                        <li key={p.entity_id} className="ask-card">
                          <span className="ask-card-name">{p.title}</span>
                          <Link
                            className="ask-card-link"
                            href={localePath(locale, `/procedures/${p.metadata.slug}/prices?state=NH`)}
                          >
                            {t.labelPrices} →
                          </Link>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </div>
          ),
        )}
        {busy ? (
          <div className="ask-turn ask-assistant ask-loading" aria-live="assertive">
            <span className="ask-role">{t.assistant}</span>
            <p className="ask-loading-text">{t.loading}</p>
          </div>
        ) : null}
        <div ref={endRef} />
      </div>

      <form
        className="ask-input-row"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
      >
        <label className="sr-only" htmlFor="ask-input">
          {t.placeholder}
        </label>
        <input
          id="ask-input"
          className="ask-input"
          type="text"
          value={input}
          placeholder={t.placeholder}
          onChange={(e) => setInput(e.target.value)}
          autoComplete="off"
          disabled={busy}
        />
        <button className="ask-send" type="submit" disabled={busy || !input.trim()}>
          {t.send}
        </button>
      </form>
      <p className="ask-privacy">{t.privacyHint}</p>
    </div>
  );
}
