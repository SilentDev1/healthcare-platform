import { Suspense } from "react";
import type { Metadata } from "next";
import { AskCarevero } from "./AskCarevero";
import { askMessages } from "../../lib/ask-i18n";
import { requestLocale } from "../../lib/i18n-server";

// Conversation-specific content is not useful to index and may contain user text.
export const metadata: Metadata = {
  title: "Ask Carevero",
  robots: { index: false, follow: true },
};

export default async function AskPage() {
  const locale = await requestLocale();
  const t = askMessages[locale] ?? askMessages.en;
  return (
    <main className="ask-page">
      <header className="ask-header">
        <p className="eyebrow">✨ {t.navLabel}</p>
        <h1>{t.title}</h1>
        <p className="lede">{t.subtitle}</p>
      </header>
      <Suspense fallback={null}>
        <AskCarevero locale={locale} />
      </Suspense>
    </main>
  );
}
