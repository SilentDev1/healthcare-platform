"use client";
import { useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { SearchSuggestion } from "../../lib/api";

const API_URL =
  process.env.NEXT_PUBLIC_CARECOMPARE_API_URL ?? "http://127.0.0.1:8000";

export function CareSearch({
  compact = false,
  initialCare = "",
  initialLocation = "",
}: {
  compact?: boolean;
  initialCare?: string;
  initialLocation?: string;
}) {
  const router = useRouter();
  const listId = useId();
  const [care, setCare] = useState(initialCare);
  const [location, setLocation] = useState(initialLocation);
  const [items, setItems] = useState<SearchSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => {
    clearTimeout(timer.current);
    if (care.trim().length < 2) {
      setItems([]);
      return;
    }
    timer.current = setTimeout(async () => {
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
      }
    }, 200);
    return () => clearTimeout(timer.current);
  }, [care]);
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!care.trim()) return;
    const params = new URLSearchParams({ q: care.trim() });
    if (location.trim()) params.set("location", location.trim());
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
        <label htmlFor={`${listId}-care`}>What do you need?</label>
        <input
          id={`${listId}-care`}
          value={care}
          onChange={(e) => {
            setCare(e.target.value);
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
      </div>
      <div className="field">
        <label htmlFor={`${listId}-location`}>Where?</label>
        <input
          id={`${listId}-location`}
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="ZIP or city"
        />
      </div>
      <button className="button search-button" type="submit">
        Compare prices <span aria-hidden="true">→</span>
      </button>
    </form>
  );
}
