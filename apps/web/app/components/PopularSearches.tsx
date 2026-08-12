import Link from "next/link";
import type { ReactNode } from "react";
import {
  localePath,
  messages,
  type Locale,
  type Messages,
} from "../../lib/i18n";

/**
 * Phase 4.8 (§2, §32): popular-procedure shortcuts with clear, accessible icons.
 *
 * Icons are inline SVG (no emoji) and decorative (aria-hidden); the text label
 * carries meaning. The underlying procedure identity is canonical — chips route
 * through search so the canonical procedure resolves regardless of locale.
 */

interface PopularSearch {
  labelKey: keyof Messages;
  query: string;
  icon: ReactNode;
}

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

const POPULAR: PopularSearch[] = [
  {
    labelKey: "popularMriKnee",
    query: "MRI knee",
    icon: strokeIcon(
      <>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="3.2" />
      </>,
    ),
  },
  {
    labelKey: "popularCtScan",
    query: "CT scan",
    icon: strokeIcon(
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 3v18M3 12h18" />
      </>,
    ),
  },
  {
    labelKey: "popularColonoscopy",
    query: "colonoscopy",
    icon: strokeIcon(<path d="M5 4v7a7 7 0 0 0 14 0M19 11V9" />),
  },
  {
    labelKey: "popularKneeReplacement",
    query: "knee replacement",
    icon: strokeIcon(<path d="M8 3v6a4 4 0 0 0 4 4 4 4 0 0 1 4 4v4M8 13v8" />),
  },
  {
    labelKey: "popularChildbirthVaginal",
    query: "childbirth",
    icon: strokeIcon(
      <>
        <circle cx="12" cy="7" r="3" />
        <path d="M12 10v7M9 14h6M10 21l2-2 2 2" />
      </>,
    ),
  },
  {
    labelKey: "popularGallbladderRemoval",
    query: "gallbladder removal",
    icon: strokeIcon(
      <path d="M9 4h6a2 2 0 0 1 2 2c0 6-2.5 12-5 12S7 12 7 6a2 2 0 0 1 2-2Z" />,
    ),
  },
];

export function PopularSearches({
  locale,
  heading,
  viewAllLabel,
}: {
  locale: Locale;
  heading: string;
  viewAllLabel: string;
}) {
  const t = messages[locale];
  return (
    <section className="popular-search-bar" aria-label={heading}>
      <span className="popular-search-heading">{heading}</span>
      <div className="popular-search-chips">
        {POPULAR.map((item) => (
          <Link
            key={item.query}
            className="popular-chip"
            href={`${localePath(locale, "/search")}?q=${encodeURIComponent(item.query)}`}
          >
            <span className="popular-chip-icon" aria-hidden="true">
              {item.icon}
            </span>
            {t[item.labelKey]}
          </Link>
        ))}
      </div>
      <Link
        className="popular-search-all"
        href={localePath(locale, "/procedures")}
      >
        {viewAllLabel} <span aria-hidden="true">→</span>
      </Link>
    </section>
  );
}
