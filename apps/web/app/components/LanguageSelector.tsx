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
