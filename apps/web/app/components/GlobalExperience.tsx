"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { localePath, type Locale } from "../../lib/i18n";
import { askMessages } from "../../lib/ask-i18n";
import { experienceMessages } from "../../lib/experience-i18n";

const AskCarevero = dynamic(() => import("../ask/AskCarevero").then((m) => m.AskCarevero), { loading: () => <p className="experience-loading">Finding Carevero results…</p> });
export const OPEN_SEARCH = "carevero:open-search";
export const OPEN_ASK = "carevero:open-ask";

export function ExperienceTrigger({ kind, className, children, query }: { kind: "search" | "ask"; className?: string; children: React.ReactNode; query?: string }) {
  return <button type="button" className={className} onClick={(event) => window.dispatchEvent(new CustomEvent(kind === "search" ? OPEN_SEARCH : OPEN_ASK, { detail: { query }, bubbles: true }))}>{children}</button>;
}

export function GlobalExperience({ locale }: { locale: Locale }) {
  const [open, setOpen] = useState<"search" | "ask" | null>(null), [query, setQuery] = useState(""), [location, setLocation] = useState(""), [pay, setPay] = useState("");
  const dialogRef = useRef<HTMLDivElement>(null), returnFocus = useRef<HTMLElement | null>(null);
  const router = useRouter(), pathname = usePathname(), t = experienceMessages[locale], ask = askMessages[locale];
  useEffect(() => {
    const showSearch = (event: Event) => { returnFocus.current = document.activeElement as HTMLElement; setQuery((event as CustomEvent).detail?.query ?? ""); setOpen("search"); };
    const showAsk = (event: Event) => { returnFocus.current = document.activeElement as HTMLElement; setQuery((event as CustomEvent).detail?.query ?? ""); setOpen("ask"); };
    window.addEventListener(OPEN_SEARCH, showSearch); window.addEventListener(OPEN_ASK, showAsk);
    return () => { window.removeEventListener(OPEN_SEARCH, showSearch); window.removeEventListener(OPEN_ASK, showAsk); };
  }, []);
  useEffect(() => {
    if (!open) return;
    const prior = document.body.style.overflow; document.body.style.overflow = "hidden";
    const focusables = () => Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])') ?? []);
    (dialogRef.current?.querySelector<HTMLElement>("[autofocus]") ?? focusables()[0])?.focus();
    const keys = (event: KeyboardEvent) => { if (event.key === "Escape") close(); if (event.key === "Tab") { const all = focusables(); if (!all.length) return; const first = all[0], last = all.at(-1)!; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); } } };
    document.addEventListener("keydown", keys);
    return () => { document.body.style.overflow = prior; document.removeEventListener("keydown", keys); };
  }, [open]);
  function close() { setOpen(null); queueMicrotask(() => returnFocus.current?.focus()); }
  function submit(event: React.FormEvent) { event.preventDefault(); const params = new URLSearchParams({ q: query.trim() }); if (location.trim()) params.set("location", location.trim()); if (pay) params.set("pay", pay); close(); router.push(`${localePath(locale, "/search")}?${params}`); }
  if (!open) return null;
  return <div className={`experience-backdrop experience-${open}`} onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}><div ref={dialogRef} className="experience-dialog" role="dialog" aria-modal="true" aria-labelledby="experience-title">
    <button className="experience-close" type="button" onClick={close} aria-label={t.close}>×</button>
    {open === "search" ? <><p className="eyebrow">Find care</p><h2 id="experience-title">{t.findTitle}</h2><p className="experience-intro">{t.findBody}</p><form className="quick-search-form" onSubmit={submit}><label>{t.need}<input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="MRI, blood test, colonoscopy…" required /></label><label>{t.where}<input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="ZIP or city" /></label><fieldset><legend>{t.payment}</legend><div className="payment-options">{[["",t.any],["self",t.self],["insurance",t.insurance]].map(([value,label]) => <label key={value} className={pay === value ? "is-active" : ""}><input type="radio" name="pay" value={value} checked={pay === value} onChange={() => setPay(value)} />{label}</label>)}</div></fieldset><button className="button" type="submit">{t.submit} →</button></form><div className="quick-popular"><strong>{t.popular}</strong>{["MRI","CT scan","Blood tests","Colonoscopy","Mammogram","Knee replacement"].map((item) => <button key={item} onClick={() => setQuery(item)}>{item}</button>)}</div><Link className="experience-escape" href={localePath(locale,"/search")} onClick={close}>{t.fullSearch} →</Link></> : <><p className="eyebrow">✨ {ask.navLabel}</p><h2 id="experience-title">{ask.title}</h2><p className="experience-intro">{t.askBody}</p><div className="ask-drawer-conversation"><AskCarevero locale={locale} initialQuery={query} context={{ pathname }} /></div><Link className="experience-escape" href={`${localePath(locale,"/ask")}${query ? `?q=${encodeURIComponent(query)}` : ""}`} onClick={close}>{t.fullAsk} →</Link></>}
  </div></div>;
}
