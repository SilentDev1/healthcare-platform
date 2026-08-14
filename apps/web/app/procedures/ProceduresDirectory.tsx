"use client";

import { useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { Procedure, ProcedureCategory } from "../../lib/api";
import { localePath, type Locale, type Messages } from "../../lib/i18n";
import { consumerCategoryName } from "../../lib/procedureCategories";
import { ProcedureCard } from "../components/ProcedureCard";

/* ------------------------------------------------------------------ */
/* Category icon map — inline SVGs, matching PopularSearches stroke     */
/* ------------------------------------------------------------------ */

const strokeIcon = (children: ReactNode): ReactNode => (
  <svg
    viewBox="0 0 24 24"
    aria-hidden="true"
    focusable="false"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    {children}
  </svg>
);

const CATEGORY_ICONS: Record<string, ReactNode> = {
  imaging: strokeIcon(
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="3.2" />
    </>,
  ),
  laboratory: strokeIcon(
    <path d="M9 3h6M10 3v6l-5 8a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-8V3" />,
  ),
  preventive: strokeIcon(
    <>
      <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z" />
      <path d="M9 12l2 2 4-4" />
    </>,
  ),
  emergency: strokeIcon(
    <>
      <path d="M12 3v18M3 12h18" />
      <rect x="4" y="4" width="16" height="16" rx="2" />
    </>,
  ),
  maternity: strokeIcon(
    <>
      <circle cx="12" cy="7" r="3" />
      <path d="M12 10v7M9 14h6M10 21l2-2 2 2" />
    </>,
  ),
  "outpatient-surgery": strokeIcon(
    <path d="M8 4l4 4 4-4M4 12h16M8 20l4-4 4 4" />,
  ),
  "inpatient-surgery": strokeIcon(
    <path d="M3 12h18M12 3v18M7 7l10 10M17 7L7 17" />,
  ),
  cardiology: strokeIcon(
    <path d="M12 20S4 14 4 9a4 4 0 0 1 8 0 4 4 0 0 1 8 0c0 5-8 11-8 11Z" />,
  ),
  orthopedics: strokeIcon(
    <path d="M8 3v6a4 4 0 0 0 4 4 4 4 0 0 1 4 4v4M8 13v8" />,
  ),
  gastroenterology: strokeIcon(
    <path d="M5 4v7a7 7 0 0 0 14 0M19 11V9" />,
  ),
  ophthalmology: strokeIcon(
    <>
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>,
  ),
  rehabilitation: strokeIcon(
    <>
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v6M8 17l4-4 4 4" />
    </>,
  ),
};

/* ------------------------------------------------------------------ */
/* Popular search chips (subset of procedures)                          */
/* ------------------------------------------------------------------ */

const POPULAR_SLUGS = [
  "mri-knee-without-contrast",
  "ct-scan-abdomen-pelvis",
  "colonoscopy-diagnostic",
  "mammogram-screening",
  "complete-blood-count",
  "knee-replacement-total",
];

/* ------------------------------------------------------------------ */
/* Helpers                                                              */
/* ------------------------------------------------------------------ */

const TEMPLATE_PREFIX = "A consumer-friendly overview of";

function cleanDescription(proc: Procedure): string {
  if (proc.short_description.startsWith(TEMPLATE_PREFIX)) {
    if (proc.long_description) {
      const trimmed = proc.long_description.slice(0, 120);
      return trimmed.length < proc.long_description.length
        ? trimmed + "…"
        : trimmed;
    }
    return "";
  }
  return proc.short_description;
}

function procedureCountLabel(t: Messages, count: number): string {
  return count === 1
    ? t.procDirProcedureCountOne
    : t.procDirProcedureCount.replace("{count}", String(count));
}

/* ------------------------------------------------------------------ */
/* Component                                                            */
/* ------------------------------------------------------------------ */

export function ProceduresDirectory({
  procedures,
  categories: _categories,
  locale,
  messages: t,
  initialCategory,
  initialQuery,
  initialSort,
}: {
  procedures: Procedure[];
  categories: ProcedureCategory[];
  locale: Locale;
  messages: Messages;
  initialCategory?: string;
  initialQuery?: string;
  initialSort?: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeCategory = searchParams.get("category") ?? initialCategory ?? "";
  const activeQuery = searchParams.get("q") ?? initialQuery ?? "";
  const activeSort = searchParams.get("sort") ?? initialSort ?? "az";

  const [query, setQuery] = useState(activeQuery);

  /* ---- Derive URL and push state ---- */

  function pushState(updates: {
    category?: string;
    q?: string;
    sort?: string;
  }) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, val] of Object.entries(updates)) {
      if (val) params.set(key, val);
      else params.delete(key);
    }
    const qs = params.toString();
    router.replace(`/procedures${qs ? `?${qs}` : ""}`, { scroll: false });
  }

  /* ---- Build category list with counts from actual data ---- */

  const categoryMap = useMemo(() => {
    const map = new Map<string, { name: string; count: number }>();
    for (const proc of procedures) {
      const slug = proc.category.slug;
      const existing = map.get(slug);
      if (existing) {
        existing.count++;
      } else {
        map.set(slug, {
          name: consumerCategoryName(t, slug),
          count: 1,
        });
      }
    }
    return map;
  }, [procedures, t]);

  const sortedCategories = useMemo(() => {
    return Array.from(categoryMap.entries()).sort(([, a], [, b]) =>
      a.name.localeCompare(b.name),
    );
  }, [categoryMap]);

  /* ---- ED family grouping ---- */

  const edProcedures = useMemo(
    () =>
      procedures
        .filter((p) => p.slug.startsWith("ed-visit-level-"))
        .sort((a, b) => a.slug.localeCompare(b.slug)),
    [procedures],
  );

  const nonEdProcedures = useMemo(
    () => procedures.filter((p) => !p.slug.startsWith("ed-visit-level-")),
    [procedures],
  );

  /* ---- Filtered + sorted results ---- */

  const filtered = useMemo(() => {
    const q = activeQuery.toLowerCase().trim();
    const searchActive = q.length > 0;

    // When search is active, include ED procedures individually
    // When no search, exclude individual ED procedures (they go in the family card)
    let base = searchActive ? procedures : nonEdProcedures;

    // Category filter
    if (activeCategory) {
      base = base.filter((p) => p.category.slug === activeCategory);
    }

    // Search filter
    if (searchActive) {
      base = base.filter((p) => {
        const name = p.consumer_name.toLowerCase();
        const aliases = p.aliases.map((a) => a.toLowerCase());
        const catName = consumerCategoryName(t, p.category.slug).toLowerCase();
        return (
          name.includes(q) ||
          aliases.some((a) => a.includes(q)) ||
          catName.includes(q)
        );
      });
    }

    // Sort
    const sorted = [...base];
    if (activeSort === "za") {
      sorted.sort((a, b) => b.consumer_name.localeCompare(a.consumer_name));
    } else {
      sorted.sort((a, b) => a.consumer_name.localeCompare(b.consumer_name));
    }

    return sorted;
  }, [
    procedures,
    nonEdProcedures,
    activeCategory,
    activeQuery,
    activeSort,
    t,
  ]);

  /* ---- Popular chips ---- */

  const popularProcedures = useMemo(
    () =>
      POPULAR_SLUGS.map((slug) =>
        procedures.find((p) => p.slug === slug),
      ).filter(Boolean) as Procedure[],
    [procedures],
  );

  /* ---- Show ED family card? ---- */

  const showEdFamily =
    !activeQuery &&
    (!activeCategory || activeCategory === "emergency") &&
    edProcedures.length > 0;

  /* ---- Handlers ---- */

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    pushState({ q: query || undefined });
  }

  function handleClearSearch() {
    setQuery("");
    pushState({ q: undefined });
  }

  function handleCategoryClick(slug: string) {
    pushState({
      category: slug === activeCategory ? undefined : slug,
    });
  }

  function handleSortChange(e: React.ChangeEvent<HTMLSelectElement>) {
    pushState({ sort: e.target.value === "az" ? undefined : e.target.value });
  }

  function handleChipClick(proc: Procedure) {
    setQuery(proc.consumer_name);
    pushState({ q: proc.consumer_name });
  }

  /* ---- Render ---- */

  return (
    <main>
      {/* Breadcrumbs */}
      <nav className="breadcrumbs" aria-label={t.breadcrumb}>
        <Link href={localePath(locale, "/")}>{t.home}</Link>
        <span>/</span>
        <span>{t.procedures}</span>
      </nav>

      {/* Hero */}
      <div className="procdir-hero">
        <p className="eyebrow">{t.procDirEyebrow}</p>
        <h1>{t.procDirTitle}</h1>
        <p className="procdir-description">{t.procDirDescription}</p>
      </div>

      {/* Search */}
      <form className="procdir-search" onSubmit={handleSearch} role="search">
        <label htmlFor="procdir-q" className="sr-only">
          {t.procDirSearchLabel}
        </label>
        <input
          id="procdir-q"
          type="search"
          className="procdir-search-input"
          placeholder={t.procDirSearchPlaceholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoComplete="off"
        />
      </form>

      {/* Popular chips */}
      {!activeQuery && popularProcedures.length > 0 && (
        <div className="procdir-chips" aria-label={t.procDirPopularHeading}>
          <span className="procdir-chips-label">{t.procDirPopularHeading}</span>
          {popularProcedures.map((proc) => (
            <button
              key={proc.slug}
              type="button"
              className="procdir-chip"
              onClick={() => handleChipClick(proc)}
            >
              {proc.consumer_name}
            </button>
          ))}
        </div>
      )}

      {/* Mobile category tiles */}
      <div
        className="procdir-cat-tiles"
        role="navigation"
        aria-label={t.procDirCategoryNav}
      >
        <button
          type="button"
          className={`procdir-cat-tile ${!activeCategory ? "active" : ""}`}
          onClick={() => handleCategoryClick("")}
        >
          {t.procDirAllProcedures}
        </button>
        {sortedCategories.map(([slug, { name, count }]) => (
          <button
            key={slug}
            type="button"
            className={`procdir-cat-tile ${activeCategory === slug ? "active" : ""}`}
            onClick={() => handleCategoryClick(slug)}
          >
            <span className="procdir-cat-tile-icon" aria-hidden="true">
              {CATEGORY_ICONS[slug] ?? CATEGORY_ICONS.other ?? null}
            </span>
            {name}
            <span className="procdir-cat-tile-count">{count}</span>
          </button>
        ))}
      </div>

      {/* Main layout: sidebar + results */}
      <div className="procdir-layout">
        {/* Sidebar (desktop only) */}
        <aside className="procdir-sidebar" aria-label={t.procDirCategoryNav}>
          <button
            type="button"
            className="procdir-sidebar-item"
            aria-current={!activeCategory ? "true" : undefined}
            onClick={() => handleCategoryClick("")}
          >
            {t.procDirAllProcedures}
            <span className="procdir-sidebar-count">{procedures.length}</span>
          </button>
          {sortedCategories.map(([slug, { name, count }]) => (
            <button
              key={slug}
              type="button"
              className="procdir-sidebar-item"
              aria-current={activeCategory === slug ? "true" : undefined}
              onClick={() => handleCategoryClick(slug)}
            >
              <span className="procdir-sidebar-icon" aria-hidden="true">
                {CATEGORY_ICONS[slug] ?? CATEGORY_ICONS.other ?? null}
              </span>
              {name}
              <span className="procdir-sidebar-count">{count}</span>
            </button>
          ))}
        </aside>

        {/* Results */}
        <div className="procdir-results">
          {/* Header: count + sort */}
          <div className="procdir-results-header">
            <span className="procdir-results-count">
              {activeQuery && (
                <>
                  <strong>&ldquo;{activeQuery}&rdquo;</strong>
                  {" — "}
                </>
              )}
              {procedureCountLabel(t, filtered.length)}
            </span>
            <label className="procdir-sort">
              <span className="sr-only">{t.procDirSortLabel}</span>
              <select value={activeSort} onChange={handleSortChange}>
                <option value="az">{t.procDirSortAZ}</option>
                <option value="za">{t.procDirSortZA}</option>
              </select>
            </label>
          </div>

          {/* ED family card */}
          {showEdFamily && (
            <div className="procdir-ed-family">
              <div className="procdir-ed-family-header">
                <span className="procdir-card-icon" aria-hidden="true">
                  {CATEGORY_ICONS.emergency}
                </span>
                <div>
                  <h2 className="procdir-ed-family-title">
                    {t.procDirEdFamilyTitle}
                  </h2>
                  <p className="procdir-ed-family-desc">
                    {t.procDirEdFamilyDesc}
                  </p>
                </div>
              </div>
              <ul className="procdir-ed-family-list">
                {edProcedures.map((proc) => (
                  <li key={proc.id}>
                    <Link
                      href={localePath(
                        locale,
                        `/procedures/${proc.slug}/prices`,
                      )}
                    >
                      {proc.consumer_name}
                      <span className="procdir-arrow" aria-hidden="true">
                        →
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Procedure cards */}
          {filtered.length > 0 ? (
            <div className="procdir-cards">
              {filtered.map((proc) => (
                <ProcedureCard
                  key={proc.id}
                  id={proc.id}
                  slug={proc.slug}
                  name={proc.consumer_name}
                  description={cleanDescription(proc)}
                  icon={CATEGORY_ICONS[proc.category.slug] ?? null}
                  locale={locale}
                  viewPricesLabel={t.procDirViewPrices}
                />
              ))}
            </div>
          ) : (
            /* Empty state */
            <div className="procdir-empty">
              <p className="procdir-empty-title">{t.procDirNoResults}</p>
              <p className="procdir-empty-help">{t.procDirNoResultsHelp}</p>
              <button
                type="button"
                className="button secondary"
                onClick={handleClearSearch}
              >
                {t.procDirClearSearch}
              </button>
            </div>
          )}

          {/* "Don't see a service?" info card */}
          <div className="procdir-info-card">
            <strong>{t.procDirDontSeeTitle}</strong>
            <p>{t.procDirDontSeeBody}</p>
          </div>

          {/* Pricing availability notice */}
          <div className="procdir-info-card">
            <strong>{t.procDirPricingNotice}</strong>
            <p>{t.procDirPricingNoticeBody}</p>
            <Link
              className="procdir-info-link"
              href={localePath(locale, "/how-it-works")}
            >
              {t.procDirLearnPricing}
              <span aria-hidden="true"> →</span>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
