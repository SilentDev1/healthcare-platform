"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { localePath, type Locale } from "../../lib/i18n";
import { navigationMessages } from "../../lib/navigation-i18n";
import { ExperienceTrigger } from "./GlobalExperience";
import { LanguageSelector } from "./LanguageSelector";

export function NavigationHeader({
  locale,
  languageLabel,
}: {
  locale: Locale;
  languageLabel: string;
}) {
  const t = navigationMessages[locale],
    pathname = usePathname();
  const [menu, setMenu] = useState<"care" | "about" | null>(null),
    [mobileOpen, setMobileOpen] = useState(false);
  const desktopRef = useRef<HTMLDivElement>(null),
    mobileRef = useRef<HTMLDivElement>(null),
    mobileButtonRef = useRef<HTMLButtonElement>(null);
  const careActive = /\/(procedures|map|search)(\/|$)/.test(pathname),
    providersActive = /\/providers(\/|$)/.test(pathname);

  useEffect(() => {
    const outside = (event: MouseEvent) => {
      if (!desktopRef.current?.contains(event.target as Node)) setMenu(null);
    };
    const keys = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenu(null);
        if (mobileOpen) {
          setMobileOpen(false);
          queueMicrotask(() => mobileButtonRef.current?.focus());
        }
      }
      if (event.key === "Tab" && mobileOpen) {
        const all = Array.from(
          mobileRef.current?.querySelectorAll<HTMLElement>(
            'button, a[href], select, [tabindex]:not([tabindex="-1"])',
          ) ?? [],
        );
        if (!all.length) return;
        const first = all[0],
          last = all.at(-1)!;
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", keys);
    return () => {
      document.removeEventListener("mousedown", outside);
      document.removeEventListener("keydown", keys);
    };
  }, [mobileOpen]);
  useEffect(() => {
    if (!mobileOpen) return;
    const prior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    mobileRef.current?.querySelector<HTMLElement>("button, a[href]")?.focus();
    return () => {
      document.body.style.overflow = prior;
    };
  }, [mobileOpen]);
  const closeMobile = () => setMobileOpen(false);

  return (
    <>
      <div className="desktop-navigation" ref={desktopRef}>
        <nav aria-label="Primary navigation">
          <div className="nav-menu-wrap">
            <button
              className={careActive ? "is-active" : ""}
              type="button"
              aria-haspopup="menu"
              aria-expanded={menu === "care"}
              onClick={() => setMenu(menu === "care" ? null : "care")}
            >
              {t.findCare} <span aria-hidden="true">⌄</span>
            </button>
            {menu === "care" && (
              <div className="nav-dropdown" role="menu">
                <ExperienceTrigger
                  kind="search"
                  className="nav-dropdown-action"
                  onTrigger={() => setMenu(null)}
                >
                  <strong>{t.searchPrices}</strong>
                  <small>{t.searchPricesHelp}</small>
                </ExperienceTrigger>
                <Link
                  role="menuitem"
                  href={localePath(locale, "/procedures")}
                  onClick={() => setMenu(null)}
                >
                  <strong>{t.browseProcedures}</strong>
                  <small>{t.browseProceduresHelp}</small>
                </Link>
                <Link
                  role="menuitem"
                  href={localePath(locale, "/map")}
                  onClick={() => setMenu(null)}
                >
                  <strong>{t.exploreMap}</strong>
                  <small>{t.exploreMapHelp}</small>
                </Link>
                <Link
                  role="menuitem"
                  href={`${localePath(locale, "/search")}?pay=self`}
                  onClick={() => setMenu(null)}
                >
                  <strong>{t.selfPay}</strong>
                  <small>{t.selfPayHelp}</small>
                </Link>
              </div>
            )}
          </div>
          <Link
            className={providersActive ? "is-active" : ""}
            href={localePath(locale, "/providers")}
          >
            {t.providers}
          </Link>
          <Link
            className={pathname.includes("how-it-works") ? "is-active" : ""}
            href={localePath(locale, "/how-it-works")}
          >
            {t.howItWorks}
          </Link>
          <div className="nav-menu-wrap">
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={menu === "about"}
              onClick={() => setMenu(menu === "about" ? null : "about")}
            >
              {t.about} <span aria-hidden="true">⌄</span>
            </button>
            {menu === "about" && (
              <div className="nav-dropdown nav-dropdown-about" role="menu">
                <Link
                  role="menuitem"
                  href={localePath(locale, "/how-it-works")}
                  onClick={() => setMenu(null)}
                >
                  {t.aboutCarevero}
                </Link>
                <Link
                  role="menuitem"
                  href={localePath(locale, "/about-data")}
                  onClick={() => setMenu(null)}
                >
                  {t.aboutData}
                </Link>
                <Link
                  role="menuitem"
                  href={localePath(locale, "/terms")}
                  onClick={() => setMenu(null)}
                >
                  {t.terms}
                </Link>
              </div>
            )}
          </div>
        </nav>
        <ExperienceTrigger kind="ask" className="header-ask-cta">
          ✨ {t.ask}
        </ExperienceTrigger>
        <LanguageSelector locale={locale} label={languageLabel} compact />
      </div>
      <div className="mobile-navigation-actions">
        <ExperienceTrigger kind="ask" className="mobile-ask-cta">
          ✨ {t.askShort}
        </ExperienceTrigger>
        <button
          ref={mobileButtonRef}
          className="mobile-menu-button"
          type="button"
          aria-haspopup="dialog"
          aria-expanded={mobileOpen}
          aria-label={t.menu}
          onClick={() => setMobileOpen(true)}
        >
          ☰
        </button>
      </div>
      {mobileOpen && (
        <div
          className="mobile-nav-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeMobile();
          }}
        >
          <div
            ref={mobileRef}
            className="mobile-nav-sheet"
            role="dialog"
            aria-modal="true"
            aria-label={t.menu}
          >
            <div className="mobile-nav-heading">
              <strong>{t.menu}</strong>
              <button
                type="button"
                aria-label={t.closeMenu}
                onClick={() => {
                  closeMobile();
                  queueMicrotask(() => mobileButtonRef.current?.focus());
                }}
              >
                ×
              </button>
            </div>
            <nav aria-label={t.menu}>
              <strong className="mobile-nav-section">{t.findCare}</strong>
              <ExperienceTrigger
                kind="search"
                className="mobile-nav-action"
                onTrigger={closeMobile}
              >
                {t.searchPrices}
              </ExperienceTrigger>
              <Link
                href={localePath(locale, "/procedures")}
                onClick={closeMobile}
              >
                {t.browseProcedures}
              </Link>
              <Link href={localePath(locale, "/map")} onClick={closeMobile}>
                {t.exploreMap}
              </Link>
              <Link
                href={`${localePath(locale, "/search")}?pay=self`}
                onClick={closeMobile}
              >
                {t.selfPay}
              </Link>
              <Link
                href={localePath(locale, "/providers")}
                onClick={closeMobile}
              >
                {t.providers}
              </Link>
              <Link
                href={localePath(locale, "/how-it-works")}
                onClick={closeMobile}
              >
                {t.howItWorks}
              </Link>
              <strong className="mobile-nav-section">{t.about}</strong>
              <Link
                href={localePath(locale, "/about-data")}
                onClick={closeMobile}
              >
                {t.aboutData}
              </Link>
              <Link href={localePath(locale, "/terms")} onClick={closeMobile}>
                {t.terms}
              </Link>
              <div className="mobile-language">
                <span>{languageLabel}</span>
                <LanguageSelector locale={locale} label={languageLabel} />
              </div>
            </nav>
          </div>
        </div>
      )}
    </>
  );
}
