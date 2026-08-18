"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FacilityImage } from "../components/FacilityImage";
import { askMessages } from "../../lib/ask-i18n";
import { localePath, type Locale } from "../../lib/i18n";

interface ResolveResponse { domain: string; intent_type: string; candidate_slugs: string[]; clarification_needed: boolean; refusal_message: string | null; }
interface SearchItem { entity_type: string; entity_id: string; title: string; subtitle: string; location: string | null; metadata: { slug?: string; image_url?: string | null; image_alt?: string | null; image_attribution?: string | null; }; }
interface SearchResponse { items?: SearchItem[]; capability_locations?: SearchItem[]; intent_type?: string; clarification_needed?: boolean; canonical_category_slug?: string | null; canonical_capability?: string | null; location_text?: string | null; payment_context?: string | null; }
interface PriceRow { facility_id: string; facility_name: string; city: string | null; location_name?: string | null; location_type?: string | null; cash_price_min: number | string | null; negotiated_price_min: number | string | null; included_component_scope?: string | null; }
type Kind = "clarification" | "prices" | "providers" | "explanation" | "medical" | "out_of_scope" | "error" | "empty";
type Turn = { role: "user"; text: string } | { role: "assistant"; kind: Kind; text: string; followup?: string; category?: string; procedures?: SearchItem[]; providers?: SearchItem[]; prices?: { slug: string; rows: PriceRow[] }; selfPay?: boolean; };

function money(value: number | string | null) { const n = Number(value); return value !== null && value !== "" && Number.isFinite(n) ? `$${Math.round(n).toLocaleString()}` : null; }
function definitionFor(question: string) {
  const q = question.toLowerCase();
  if (/(what|mean|define|explain)/.test(q) && /discounted cash price|cash price/.test(q)) return "A discounted cash price is a provider’s published price for paying directly without using insurance. Confirm the price and what it includes with the provider before receiving care.";
  if (/(what|mean|define|explain)/.test(q) && /negotiated (rate|price)/.test(q)) return "A negotiated rate is an amount a provider and health plan have agreed on for a covered service. It is not necessarily what an individual patient will pay.";
  return null;
}

export function ContextChips({ selfPay, category }: { selfPay?: boolean; category?: string }) {
  if (!selfPay && !category) return null;
  return <div className="ask-context" aria-label="Search context">{selfPay ? <span className="ask-context-chip ask-context-pay">Self-pay / no insurance</span> : null}{category ? <span className="ask-context-chip">{category === "laboratory" ? "Laboratory" : category.replaceAll("_", " ")}</span> : null}</div>;
}

function ProcedureChoiceCard({ item, locale, selfPay }: { item: SearchItem; locale: Locale; selfPay?: boolean }) {
  const label = selfPay ? "Compare self-pay prices" : "Compare published prices";
  return <li className="ask-result-card ask-procedure-card"><div><h3>{item.title}</h3>{item.subtitle && item.subtitle !== item.title ? <p>{item.subtitle}</p> : null}</div><Link href={localePath(locale, `/procedures/${item.metadata.slug}/prices?state=NH${selfPay ? "&pay=self" : ""}`)} aria-label={`${label}: ${item.title}`}>{label} <span aria-hidden="true">→</span></Link></li>;
}

function ProviderCard({ item, locale, unavailable }: { item: SearchItem; locale: Locale; unavailable: string }) {
  return <li className="ask-result-card ask-provider-card"><FacilityImage name={item.title} imageUrl={item.metadata.image_url} imageAlt={item.metadata.image_alt} attribution={item.metadata.image_attribution} placeholderLabel={null} variant="thumb" /><div className="ask-result-body"><h3>{item.title}</h3><p>{item.subtitle || item.location}</p><span className="ask-no-price">{unavailable}</span></div><Link href={localePath(locale, `/hospitals/${item.entity_id}`)} aria-label={`View details for ${item.title}`}>View details</Link></li>;
}

function PriceCard({ row, locale, selfPay, unavailable }: { row: PriceRow; locale: Locale; selfPay?: boolean; unavailable: string }) {
  const cash = money(row.cash_price_min), negotiated = money(row.negotiated_price_min), shown = selfPay ? cash : cash ?? negotiated;
  return <li className="ask-result-card ask-price-card"><div className="ask-result-body"><h3>{row.facility_name}</h3><p>{[row.location_name, row.city, row.location_type?.replaceAll("_", " ")].filter(Boolean).join(" · ")}</p>{shown ? <p className="ask-price"><span>{cash && (selfPay || !negotiated) ? "Published cash/self-pay price" : "Published price"}</span>{shown}</p> : <span className="ask-no-price">{unavailable}</span>}{row.included_component_scope ? <p className="ask-scope">{row.included_component_scope}</p> : null}</div><Link href={localePath(locale, `/hospitals/${row.facility_id}`)} aria-label={`View price details for ${row.facility_name}`}>View details</Link></li>;
}

export function AskCarevero({ locale, initialQuery = "", context }: { locale: Locale; initialQuery?: string; context?: { pathname?: string } }) {
  const t = askMessages[locale] ?? askMessages.en, params = useSearchParams();
  const [turns, setTurns] = useState<Turn[]>([]), [input, setInput] = useState(""), [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null), started = useRef(false);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, busy]);

  async function ask(question: string) {
    const q = question.trim(); if (!q || busy) return;
    setInput(""); setTurns((p) => [...p, { role: "user", text: q }]); setBusy(true);
    try {
      let resolve: ResolveResponse | null = null;
      try { const r = await fetch("/api/ask/resolve", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: q, locale }) }); if (r.ok) resolve = await r.json() as ResolveResponse; } catch { resolve = null; }
      if (resolve?.domain === "medical_advice") { setTurns((p) => [...p, { role: "assistant", kind: "medical", text: resolve?.refusal_message || t.medicalBoundary, followup: t.medicalFollowup }]); return; }
      if (resolve?.domain === "out_of_scope") { setTurns((p) => [...p, { role: "assistant", kind: "out_of_scope", text: resolve?.refusal_message || t.outOfScope }]); return; }
      const definition = definitionFor(q); if (definition) { setTurns((p) => [...p, { role: "assistant", kind: "explanation", text: definition }]); return; }
      const sr = await fetch(`/api/ask/search?q=${encodeURIComponent(q)}&locale=${encodeURIComponent(locale)}`); const search: SearchResponse = sr.ok ? await sr.json() : {};
      const items = search.items ?? [], procedures = items.filter((x) => x.entity_type === "procedure" && x.metadata.slug), facilities = items.filter((x) => x.entity_type === "facility");
      const providers = [...(search.capability_locations ?? []), ...facilities].filter((x, i, all) => all.findIndex((y) => y.entity_id === x.entity_id) === i);
      const selfPay = search.payment_context === "self_pay", category = search.canonical_category_slug ?? (resolve?.intent_type === "category" ? resolve.candidate_slugs[0] : undefined);
      const categoryRequest = search.intent_type === "category" || resolve?.intent_type === "category" || Boolean(search.clarification_needed && procedures.length > 1);
      if (categoryRequest && procedures.length) {
        const text = category === "laboratory" ? (selfPay ? "Sure — I can help you compare published self-pay lab prices. “Blood test” can mean several different tests, so choose the one you need below." : "Blood work can refer to several lab tests. Choose the test you need to compare published prices.") : "This category includes several services. Choose the one you need to compare published prices.";
        setTurns((p) => [...p, { role: "assistant", kind: "clarification", text, category, procedures: procedures.slice(0, 6), selfPay }]); return;
      }
      const slug = procedures[0]?.metadata.slug ?? (resolve?.intent_type === "procedure" ? resolve.candidate_slugs[0] : undefined);
      if (slug) {
        let rows: PriceRow[] = []; try { const pr = await fetch(`/api/ask/prices?slug=${encodeURIComponent(slug)}&state=NH&page_size=4`); rows = pr.ok ? (await pr.json()).items ?? [] : []; } catch { rows = []; }
        setTurns((p) => [...p, { role: "assistant", kind: rows.length ? "prices" : "clarification", text: rows.length ? (selfPay ? "Here are published self-pay prices Carevero has for this service." : "Here are published prices Carevero has for this service.") : "I found the service, but Carevero does not currently have published prices for it. You can still open the comparison page for details.", procedures: rows.length ? undefined : procedures.slice(0, 1), prices: rows.length ? { slug, rows } : undefined, selfPay }]); return;
      }
      if (providers.length) { setTurns((p) => [...p, { role: "assistant", kind: "providers", text: search.location_text ? `Here are verified provider locations near ${search.location_text}.` : "Here are verified provider locations that match your search.", providers: providers.slice(0, 6), category: search.canonical_capability ?? category, selfPay }]); return; }
      setTurns((p) => [...p, { role: "assistant", kind: "empty", text: t.noResults }]);
    } catch { setTurns((p) => [...p, { role: "assistant", kind: "error", text: t.error }]); } finally { setBusy(false); }
  }

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const q = initialQuery || params.get("q");
    if (q) queueMicrotask(() => void ask(q));
    // Context plumbing is intentionally identifiers-only. The current Ask API does
    // not yet accept this field, so it is not used to fabricate contextual answers.
    void context;
    // Deep-link initialization is intentionally run once; subsequent turns are user-driven.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <div className="ask-shell"><p className="ask-safety" role="note">{t.safety}</p><div className="ask-convo" role="log" aria-live="polite" aria-relevant="additions text">
    {turns.length === 0 ? <div className="ask-welcome"><h2>What can I help you find?</h2><p>Start with a procedure, provider, place, or price question.</p><div className="ask-starters">{t.starters.map((s) => <button key={s} type="button" className="ask-chip" onClick={() => void ask(s)}>{s}</button>)}</div></div> : null}
    {turns.map((turn, i) => turn.role === "user" ? <article key={i} className="ask-turn ask-user" aria-label={`${t.you} said`}><span className="ask-role">{t.you}</span><p>{turn.text}</p></article> : <article key={i} className={`ask-turn ask-assistant ask-${turn.kind}`} aria-label={`${t.assistant} response`}><span className="ask-role">{t.assistant}</span><p className="ask-response-text">{turn.text}</p>{turn.followup ? <p className="ask-followup">{turn.followup}</p> : null}<ContextChips selfPay={turn.selfPay} category={turn.category} />{turn.selfPay ? <p className="ask-payment-note">We’ll prioritize published cash/self-pay prices where available.</p> : null}
      {turn.procedures?.length ? <ul className="ask-result-list" aria-label="Procedure choices">{turn.procedures.map((x) => <ProcedureChoiceCard key={x.entity_id} item={x} locale={locale} selfPay={turn.selfPay} />)}</ul> : null}
      {turn.providers?.length ? <ul className="ask-result-list" aria-label="Provider locations">{turn.providers.map((x) => <ProviderCard key={x.entity_id} item={x} locale={locale} unavailable={t.priceNotAvailable} />)}</ul> : null}
      {turn.prices?.rows.length ? <><ul className="ask-result-list" aria-label="Published price results">{turn.prices.rows.map((x, j) => <PriceCard key={`${x.facility_id}-${j}`} row={x} locale={locale} selfPay={turn.selfPay} unavailable={t.priceNotAvailable} />)}</ul><Link className="ask-compare-all" href={localePath(locale, `/procedures/${turn.prices.slug}/prices?state=NH${turn.selfPay ? "&pay=self" : ""}`)}>{turn.selfPay ? "Compare all self-pay prices" : "Compare all published prices"} →</Link></> : null}
      {["medical", "out_of_scope", "empty"].includes(turn.kind) ? <div className="ask-safe-actions"><Link href={localePath(locale, "/procedures")}>Browse procedures</Link><Link href={localePath(locale, "/hospitals")}>Find providers</Link></div> : null}</article>)}
    {busy ? <div className="ask-turn ask-assistant ask-loading" role="status"><span className="ask-role">{t.assistant}</span><p className="ask-loading-text">{t.loading}</p></div> : null}<div ref={endRef} /></div>
    <div className="ask-composer-wrap"><form className="ask-input-row" onSubmit={(e) => { e.preventDefault(); void ask(input); }}><label className="sr-only" htmlFor="ask-input">{t.placeholder}</label><input id="ask-input" className="ask-input" value={input} placeholder={t.placeholder} onChange={(e) => setInput(e.target.value)} autoComplete="off" disabled={busy} /><button className="ask-send" type="submit" disabled={busy || !input.trim()} aria-label={t.send}>{t.send} <span aria-hidden="true">→</span></button></form><p className="ask-privacy">{t.privacyHint}</p></div></div>;
}
