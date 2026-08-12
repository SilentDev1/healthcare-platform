"use client";

import { usePathname } from "next/navigation";
import { isLocale, type Locale } from "../../lib/i18n";

/**
 * Client-side locale resolution for `"use client"` pages that are the route
 * itself (search, map) and cannot receive a server-resolved locale prop.
 *
 * Precedence mirrors `proxy.ts` (URL prefix wins over cookie): the middleware
 * rewrites `/vi/…` → `/…` for rendering but the browser URL keeps the prefix,
 * so `usePathname()` still exposes it. When the locale comes from the
 * `carevero-locale` cookie without a URL prefix, fall back to that cookie.
 */
export function useLocale(): Locale {
  const pathname = usePathname();
  const prefix = pathname.split("/").filter(Boolean)[0];
  if (isLocale(prefix) && prefix !== "en") return prefix;
  if (typeof document !== "undefined") {
    const match = document.cookie.match(/(?:^|;\s*)carevero-locale=([^;]+)/);
    const cookieLocale = match?.[1];
    if (isLocale(cookieLocale)) return cookieLocale;
  }
  return "en";
}
