"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { capabilityLabel, localePath, type Locale } from "../../lib/i18n";
import type { DirectoryStrings } from "../../lib/directory-i18n";

interface Option {
  value: string;
  label: string;
}
interface CapOption {
  capability: string;
  location_count: number;
}

/**
 * Always-visible provider-directory controls (desktop) + a mobile filter drawer.
 * URL-driven: every change navigates to /providers with updated query params and
 * resets to page 1, so filter state is shareable and back/forward works. No data
 * is fetched here — the server page re-renders from the URL.
 */
export function DirectoryControls({
  locale,
  t,
  current,
  allCount,
  states,
  regions,
  capabilities,
  quickCount,
}: {
  locale: Locale;
  t: DirectoryStrings;
  current: {
    q: string;
    capability: string;
    region: string;
    has: string;
    sort: string;
    state: string;
    view: string;
    size: string;
  };
  allCount: number;
  states: Option[];
  regions: Option[];
  capabilities: CapOption[];
  quickCount: number;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showAllChips, setShowAllChips] = useState(false);
  const [searchText, setSearchText] = useState(current.q);

  const go = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    // Any filter change (other than paging itself) returns to page 1.
    if (!("page" in updates)) next.delete("page");
    const qs = next.toString();
    router.push(`${localePath(locale, "/providers")}${qs ? `?${qs}` : ""}`);
  };

  const activeFilterCount =
    (current.capability ? 1 : 0) +
    (current.region ? 1 : 0) +
    (current.has ? 1 : 0) +
    (current.state && current.state !== "NH" ? 1 : 0) +
    (current.sort && current.sort !== "name" ? 1 : 0);

  const topChips = showAllChips ? capabilities : capabilities.slice(0, 6);
  const hasMoreChips = capabilities.length > 6;

  const typeSelect = (id: string) => (
    <select
      id={id}
      value={current.capability}
      onChange={(e) => go({ capability: e.target.value || null })}
    >
      <option value="">{t.allTypes}</option>
      {capabilities.map((c) => (
        <option key={c.capability} value={c.capability}>
          {capabilityLabel(c.capability, locale)} ({c.location_count})
        </option>
      ))}
    </select>
  );
  const hasSelect = (id: string) => (
    <select id={id} value={current.has} onChange={(e) => go({ has: e.target.value || null })}>
      <option value="">{t.hasPricesAny}</option>
      <option value="yes">{t.hasPricesYes}</option>
      <option value="no">{t.hasPricesNo}</option>
    </select>
  );
  const sortSelect = (id: string) => (
    <select id={id} value={current.sort} onChange={(e) => go({ sort: e.target.value || null })}>
      <option value="name">{t.sortNameAsc}</option>
      <option value="name_desc">{t.sortNameDesc}</option>
    </select>
  );
  const stateSelect = (id: string) => (
    <select id={id} value={current.state} onChange={(e) => go({ state: e.target.value || null })}>
      {states.map((s) => (
        <option key={s.value} value={s.value}>
          {s.label}
        </option>
      ))}
    </select>
  );
  const regionSelect = (id: string) => (
    <select
      id={id}
      value={current.region}
      onChange={(e) => go({ region: e.target.value || null })}
      aria-label={t.filterRegionLabel}
    >
      <option value="">{t.allRegions}</option>
      {regions.map((r) => (
        <option key={r.value} value={r.value}>
          {r.label}
        </option>
      ))}
    </select>
  );

  return (
    <div className="pd-controls">
      {/* Row 1: search + primary selects (always visible on desktop) */}
      <div className="pd-row pd-row-main">
        <form
          className="pd-search"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            go({ q: searchText.trim() || null });
          }}
        >
          <label className="sr-only" htmlFor="pd-search">
            {t.searchLabel}
          </label>
          <input
            id="pd-search"
            type="search"
            value={searchText}
            placeholder={t.searchPlaceholder}
            onChange={(e) => setSearchText(e.target.value)}
            autoComplete="off"
          />
          <button type="submit" className="button pd-search-btn">
            {t.search}
          </button>
        </form>

        <div className="pd-field pd-desktop-field">
          <label htmlFor="pd-type">{t.providerType}</label>
          {typeSelect("pd-type")}
        </div>
        <div className="pd-field pd-desktop-field">
          <label htmlFor="pd-has">{t.hasPrices}</label>
          {hasSelect("pd-has")}
        </div>
        <div className="pd-field pd-desktop-field">
          <label htmlFor="pd-sort">{t.sortBy}</label>
          {sortSelect("pd-sort")}
        </div>
        {activeFilterCount > 0 || current.q ? (
          <button
            type="button"
            className="pd-clear"
            onClick={() =>
              router.push(localePath(locale, "/providers"))
            }
          >
            {t.clear}
          </button>
        ) : null}

        {/* Mobile: open the filter drawer */}
        <button
          type="button"
          className="pd-filters-btn"
          onClick={() => setDrawerOpen(true)}
          aria-haspopup="dialog"
        >
          {t.filters}
          {activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
        </button>
      </div>

      {/* Row 2: capability quick-filter chips with real counts */}
      <div className="pd-chips" role="group" aria-label={t.providerType}>
        <button
          type="button"
          className={`pd-chip${!current.capability ? " pd-chip-on" : ""}`}
          aria-pressed={!current.capability}
          onClick={() => go({ capability: null })}
        >
          {t.allChip} ({allCount})
        </button>
        {topChips.map((c) => (
          <button
            key={c.capability}
            type="button"
            className={`pd-chip${current.capability === c.capability ? " pd-chip-on" : ""}`}
            aria-pressed={current.capability === c.capability}
            onClick={() =>
              go({ capability: current.capability === c.capability ? null : c.capability })
            }
          >
            {capabilityLabel(c.capability, locale)} ({c.location_count})
          </button>
        ))}
        {hasMoreChips ? (
          <button
            type="button"
            className="pd-chip pd-chip-more"
            aria-expanded={showAllChips}
            onClick={() => setShowAllChips((v) => !v)}
          >
            {t.more} {showAllChips ? "▲" : "▼"}
          </button>
        ) : null}
      </div>

      {/* Row 3: geography + result notice + view switcher */}
      <div className="pd-row pd-row-context">
        <div className="pd-field pd-desktop-field">
          <label htmlFor="pd-state">{t.state}</label>
          {stateSelect("pd-state")}
        </div>
        <div className="pd-field pd-desktop-field">
          <label htmlFor="pd-region">{t.region}</label>
          {regionSelect("pd-region")}
        </div>
        <p className="pd-notice" role="note">
          <span aria-hidden="true">ⓘ</span> {t.priceNotice}
        </p>
        <div className="pd-views" role="group" aria-label={t.viewSwitcherLabel}>
          {(["list", "grid", "map"] as const).map((v) => (
            <button
              key={v}
              type="button"
              className={`pd-view${current.view === v ? " pd-view-on" : ""}`}
              aria-pressed={current.view === v}
              onClick={() => go({ view: v === "list" ? null : v })}
            >
              {v === "list" ? t.viewList : v === "grid" ? t.viewGrid : t.viewMap}
            </button>
          ))}
        </div>
      </div>

      {/* Mobile filter drawer */}
      {drawerOpen ? (
        <div
          className="pd-drawer-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={t.filters}
          onClick={() => setDrawerOpen(false)}
        >
          <div className="pd-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="pd-drawer-head">
              <strong>{t.filters}</strong>
              <button type="button" className="pd-drawer-close" onClick={() => setDrawerOpen(false)}>
                {t.closeFilters}
              </button>
            </div>
            <div className="pd-field">
              <label htmlFor="pd-type-m">{t.providerType}</label>
              {typeSelect("pd-type-m")}
            </div>
            <div className="pd-field">
              <label htmlFor="pd-state-m">{t.state}</label>
              {stateSelect("pd-state-m")}
            </div>
            <div className="pd-field">
              <label htmlFor="pd-region-m">{t.region}</label>
              {regionSelect("pd-region-m")}
            </div>
            <div className="pd-field">
              <label htmlFor="pd-has-m">{t.hasPrices}</label>
              {hasSelect("pd-has-m")}
            </div>
            <div className="pd-field">
              <label htmlFor="pd-sort-m">{t.sortBy}</label>
              {sortSelect("pd-sort-m")}
            </div>
            <button type="button" className="button pd-drawer-apply" onClick={() => setDrawerOpen(false)}>
              {t.applyFilters} ({quickCount})
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
