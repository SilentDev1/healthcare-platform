"use client";

import { useState } from "react";
import { messages, type Locale } from "../../lib/i18n";

export function ShareComparison({ locale = "en" }: { locale?: Locale }) {
  const t = messages[locale] ?? messages.en;
  const [status, setStatus] = useState("");

  async function share() {
    const data = {
      title: t.shareTitle,
      text: t.shareText,
      url: window.location.href,
    };
    try {
      if (navigator.share) {
        await navigator.share(data);
        setStatus(t.shareShared);
      } else {
        await navigator.clipboard.writeText(data.url);
        setStatus(t.shareCopied);
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setStatus(t.shareFailed);
    }
  }

  return (
    <div className="share-action">
      <button className="button secondary" type="button" onClick={share}>
        {t.shareComparison}
      </button>
      <span className="field-help" role="status" aria-live="polite">
        {status}
      </span>
    </div>
  );
}
