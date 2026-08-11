"use client";
import { useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { SearchSuggestion } from "../../lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export function CareSearch({
  compact = false,
  initialCare = "",
  initialLocation = "",
  initialPayer = "",
  showInsurance = false,
}: {
  compact?: boolean;
  initialCare?: string;
  initialLocation?: string;
  initialPayer?: string;
  showInsurance?: boolean;
}) {
  const router = useRouter();
  const listId = useId();
  const [care, setCare] = useState(initialCare);
  const [location, setLocation] = useState(initialLocation);
  const [payer, setPayer] = useState(initialPayer);
  const [payers, setPayers] = useState<Array<{ slug: string; name: string }>>(
    [],
  );
  const [items, setItems] = useState<SearchSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [suggesting, setSuggesting] = useState(false);
  const [locationError, setLocationError] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => {
    clearTimeout(timer.current);
    if (care.trim().length < 2) {
      return;
    }
    timer.current = setTimeout(async () => {
      setSuggesting(true);
      try {
        const response = await fetch(
          `${API_URL}/api/v1/search/suggestions?q=${encodeURIComponent(care)}&limit=7`,
        );
        if (response.ok) {
          setItems(await response.json());
          setOpen(true);
        }
      } catch {
        setItems([]);
      } finally {
        setSuggesting(false);
      }
    }, 200);
    return () => clearTimeout(timer.current);
  }, [care]);
  useEffect(() => {
    if (!showInsurance) return;
    fetch(`${API_URL}/api/v1/pricing/payers`)
      .then((response) => (response.ok ? response.json() : []))
      .then((value: Array<{ slug: string; name: string }>) => setPayers(value))
      .catch(() => setPayers([]));
  }, [showInsurance]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!care.trim()) return;
    if (/^\d+$/.test(location.trim()) && !/^\d{5}$/.test(location.trim())) {
      setLocationError("Enter a 5-digit ZIP code or a city name.");
      return;
    }
    setLocationError("");
    const params = new URLSearchParams({ q: care.trim() });
    if (location.trim()) params.set("location", location.trim());
    if (payer) params.set("payer", payer);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/search?${new URLSearchParams({ q: care.trim(), page_size: "5" })}`,
      );
      if (response.ok) {
        const data = (await response.json()) as {
          items?: Array<{
            entity_type: string;
            metadata?: { slug?: string };
          }>;
        };
        const procedure = data.items?.find(
          (item) => item.entity_type === "procedure" && item.metadata?.slug,
        );
        if (procedure?.metadata?.slug) {
          const priceParams = new URLSearchParams();
          if (location.trim()) priceParams.set("location", location.trim());
          if (payer) priceParams.set("payer", payer);
          const query = priceParams.size ? `?${priceParams}` : "";
          router.push(`/procedures/${procedure.metadata.slug}/prices${query}`);
          return;
        }
      }
    } catch {
      // The complete search page remains the resilient fallback.
    }
    router.push(`/search?${params}`);
  }
  function keyDown(event: React.KeyboardEvent) {
    if (!open || !items.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((active + 1) % items.length);
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((active - 1 + items.length) % items.length);
    }
    if (event.key === "Escape") setOpen(false);
    if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      setCare(items[active].title);
      setOpen(false);
    }
  }
  return (
    <form
      className={`care-search ${compact ? "compact" : ""}`}
      onSubmit={submit}
    >
      <div className="field autocomplete">
        <label htmlFor={`${listId}-care`}>
          {compact ? "What do you need?" : "1. Procedure or service"}
        </label>
        <input
          id={`${listId}-care`}
          value={care}
          onChange={(e) => {
            const nextCare = e.target.value;
            setCare(nextCare);
            if (nextCare.trim().length < 2) {
              setItems([]);
              setOpen(false);
            }
            setActive(-1);
          }}
          onKeyDown={keyDown}
          onFocus={() => items.length && setOpen(true)}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={
            active >= 0 ? `${listId}-${active}` : undefined
          }
          placeholder="MRI, colonoscopy, knee replacement…"
          autoComplete="off"
          aria-autocomplete="list"
          required
        />
        {open && items.length > 0 && (
          <ul id={listId} className="suggestions" role="listbox">
            {items.map((item, index) => (
              <li
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                key={`${item.entity_type}-${item.entity_id}`}
                onMouseDown={() => {
                  setCare(item.title);
                  setOpen(false);
                }}
              >
                <small>{item.entity_type.replaceAll("_", " ")}</small>
                <strong>{item.title}</strong>
              </li>
            ))}
          </ul>
        )}
        <span className="field-help" role="status" aria-live="polite">
          {suggesting
            ? "Finding matches…"
            : care.trim().length >= 2 && !open && items.length === 0
              ? "Press Enter to search all care and hospitals."
              : ""}
        </span>
      </div>
      <div className="field">
        <label htmlFor={`${listId}-location`}>
          {compact ? "Where?" : "2. Location"}
        </label>
        <input
          id={`${listId}-location`}
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="ZIP or city"
          autoComplete="postal-code"
          aria-describedby={`${listId}-location-help`}
        />
        <span
          id={`${listId}-location-help`}
          className={locationError ? "field-error" : "field-help"}
          role={locationError ? "alert" : undefined}
        >
          {locationError || "Optional. Use a 5-digit ZIP or city name."}
        </span>
      </div>
      {showInsurance && (
        <div className="field insurance-field">
          <label htmlFor={`${listId}-payer`}>3. Published payer / rate</label>
          <select
            id={`${listId}-payer`}
            value={payer}
            onChange={(event) => setPayer(event.target.value)}
          >
            <option value="">Any published rates</option>
            {payers.map((item) => (
              <option key={item.slug} value={item.slug}>
                {item.name}
              </option>
            ))}
          </select>
          <span className="field-help">
            Published rates do not confirm coverage or network status.
          </span>
        </div>
      )}
      <button className="button search-button" type="submit">
        Search prices <span aria-hidden="true">→</span>
      </button>
    </form>
  );
}
