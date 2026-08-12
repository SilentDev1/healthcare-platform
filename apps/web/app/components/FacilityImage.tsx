import type { CSSProperties } from "react";

/**
 * Shared facility / service-location image with a polished neutral fallback.
 *
 * Phase 4.8 (§8–11, §20, §25): result cards and comparison thumbnails must show
 * an image. Until verified organization-provided imagery exists, every facility
 * renders a deterministic, clearly-neutral Carevero placeholder — never a broken
 * image icon and never generic stock photography that could be mistaken for the
 * real hospital. When the API later supplies a verified `imageUrl`, it is used
 * directly with lazy loading; the component's contract does not change per page.
 */

function hashHue(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % 360;
  }
  return hash;
}

function initials(name: string): string {
  const words = name
    .replace(/[^A-Za-z0-9 ]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  const letters = words.slice(0, 2).map((word) => word[0]?.toUpperCase() ?? "");
  return letters.join("") || "H";
}

export function FacilityImage({
  name,
  imageUrl,
  imageAlt,
  attribution,
  placeholderLabel,
  variant = "card",
  className,
}: {
  name: string;
  imageUrl?: string | null;
  imageAlt?: string | null;
  /** Visible credit for licensed imagery (e.g. CC-BY); rendered when present. */
  attribution?: string | null;
  /** Localized aria-label for the neutral placeholder. */
  placeholderLabel?: string | null;
  variant?: "card" | "thumb";
  className?: string;
}) {
  const baseClass = `facility-image facility-image-${variant}${
    className ? ` ${className}` : ""
  }`;

  if (imageUrl) {
    return (
      <span className={baseClass}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl}
          alt={imageAlt ?? `${name} location`}
          loading="lazy"
          decoding="async"
        />
        {attribution ? (
          <span className="facility-image-credit" title={attribution}>
            {attribution}
          </span>
        ) : null}
      </span>
    );
  }

  const hue = hashHue(name);
  const style = {
    "--facility-accent": `hsl(${hue} 34% 32%)`,
    "--facility-accent-soft": `hsl(${hue} 30% 88%)`,
  } as CSSProperties;

  return (
    <span
      className={`${baseClass} facility-image-placeholder`}
      style={style}
      role="img"
      aria-label={
        placeholderLabel
          ? `${name} — ${placeholderLabel}`
          : `${name} — no verified photo available`
      }
    >
      <svg viewBox="0 0 64 64" aria-hidden="true" focusable="false">
        <rect x="14" y="22" width="36" height="30" rx="2" />
        <rect x="22" y="30" width="6" height="6" className="win" />
        <rect x="36" y="30" width="6" height="6" className="win" />
        <rect x="28" y="42" width="8" height="10" className="door" />
        <path d="M32 10v8M28 14h8" className="cross" />
      </svg>
      <span className="facility-image-initials" aria-hidden="true">
        {initials(name)}
      </span>
    </span>
  );
}
