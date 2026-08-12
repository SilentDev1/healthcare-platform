"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { localeNames, locales, type Locale } from "../../lib/i18n";

export function LanguageSelector({
  locale,
  label,
}: {
  locale: Locale;
  label: string;
}) {
  const pathname = usePathname();
  const params = useSearchParams();
  const router = useRouter();

  function switchLocale(nextLocale: Locale) {
    const pathWithoutLocale =
      pathname.replace(/^\/(es|vi|zh-TW|zh-CN)(?=\/|$)/, "") || "/";
    const localized =
      nextLocale === "en"
        ? pathWithoutLocale
        : `/${nextLocale}${pathWithoutLocale === "/" ? "" : pathWithoutLocale}`;
    const query = params.toString();
    document.cookie = `carevero-locale=${nextLocale}; Path=/; Max-Age=31536000; SameSite=Lax`;
    router.push(`${localized}${query ? `?${query}` : ""}`);
    // The locale-prefix rewrite in proxy.ts collapses every locale to the same
    // rewritten path, so the App Router cache can serve a stale RSC payload for
    // the previous language. Invalidate it so the new locale renders immediately
    // (no full-page reload; client state and query params are preserved).
    router.refresh();
  }

  return (
    <label className="language-selector">
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        value={locale}
        onChange={(event) => switchLocale(event.target.value as Locale)}
      >
        {locales.map((item) => (
          <option key={item} value={item}>
            {localeNames[item]}
          </option>
        ))}
      </select>
    </label>
  );
}
