"use client";

import { useState } from "react";

export function ShareComparison() {
  const [status, setStatus] = useState("");

  async function share() {
    const data = {
      title: "Carevero hospital price comparison",
      text: "Compare published hospital prices and CMS quality information on Carevero.",
      url: window.location.href,
    };
    try {
      if (navigator.share) {
        await navigator.share(data);
        setStatus("Comparison shared.");
      } else {
        await navigator.clipboard.writeText(data.url);
        setStatus("Comparison link copied.");
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setStatus("Unable to share. Copy the address from your browser.");
    }
  }

  return (
    <div className="share-action">
      <button className="button secondary" type="button" onClick={share}>
        Share comparison
      </button>
      <span className="field-help" role="status" aria-live="polite">
        {status}
      </span>
    </div>
  );
}
