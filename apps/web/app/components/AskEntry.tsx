"use client";

import { useState } from "react";
import { askMessages } from "../../lib/ask-i18n";
import { type Locale } from "../../lib/i18n";
import { OPEN_ASK } from "./GlobalExperience";

/**
 * "Ask Carevero" entry point. Compact by design — it is a gateway to the dedicated /ask page,
 * never a chat window embedded in the hero.
 *
 *  - variant="home": heading + one input + CTA + safe starter chips (homepage, below search).
 *  - variant="inline": a single contextual link that passes a preset grounded query (procedure /
 *    provider / comparison pages). Only a short preset prompt is sent — never page/database dumps.
 */
export function AskEntry({
  locale,
  variant = "home",
  presetQuery,
  inlineLabel,
}: {
  locale: Locale;
  variant?: "home" | "inline";
  presetQuery?: string;
  inlineLabel?: string;
}) {
  const t = askMessages[locale] ?? askMessages.en;
  const [value, setValue] = useState("");

  function go(q: string) {
    const query = q.trim();
    window.dispatchEvent(new CustomEvent(OPEN_ASK, { detail: { query } }));
  }

  if (variant === "inline") {
    return (
      <button type="button" className="ask-inline-entry" onClick={() => go(presetQuery ?? "")}>
        <span aria-hidden="true">✨</span> {inlineLabel ?? t.navLabel}
      </button>
    );
  }

  return (
    <section className="ask-entry" aria-label={t.homeHeading}>
      <p className="ask-entry-heading">
        <span aria-hidden="true">✨</span> {t.homeHeading}
      </p>
      <p className="ask-entry-sub">{t.homeSubhead}</p>
      <form
        className="ask-entry-form"
        onSubmit={(e) => {
          e.preventDefault();
          go(value);
        }}
      >
        <label className="sr-only" htmlFor="ask-entry-input">
          {t.homePlaceholder}
        </label>
        <input
          id="ask-entry-input"
          className="ask-entry-input"
          type="text"
          value={value}
          placeholder={t.homePlaceholder}
          onChange={(e) => setValue(e.target.value)}
          autoComplete="off"
        />
        <button className="ask-entry-cta" type="submit">
          {t.homeCta} →
        </button>
      </form>
      <div className="ask-entry-chips">
        {t.starters.slice(0, 4).map((s) => (
          <button key={s} type="button" className="chip" onClick={() => go(s)}>
            {s}
          </button>
        ))}
      </div>
    </section>
  );
}
