"use client";

import Link from "next/link";
import { useMemo, useSyncExternalStore } from "react";

interface CompareChoice {
  key: string;
  facilityId: string;
  locationId: string;
  name: string;
}

function storageKey(procedureSlug: string) {
  return `careveroCompareV1:${procedureSlug}`;
}

function parseChoices(value: string): CompareChoice[] {
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) ? (parsed as CompareChoice[]).slice(0, 3) : [];
  } catch {
    return [];
  }
}

function subscribe(onStoreChange: () => void) {
  window.addEventListener("carevero:selection", onStoreChange);
  return () => window.removeEventListener("carevero:selection", onStoreChange);
}

function useChoices(procedureSlug: string) {
  const serialized = useSyncExternalStore(
    subscribe,
    () => sessionStorage.getItem(storageKey(procedureSlug)) ?? "[]",
    () => "[]",
  );
  return useMemo(() => parseChoices(serialized), [serialized]);
}

export function CompareSelect({
  facilityId,
  locationId,
  name,
  procedureSlug,
}: {
  facilityId: string;
  locationId: string;
  name: string;
  procedureSlug: string;
}) {
  const key = `${facilityId}~${locationId}`;
  const selected = useChoices(procedureSlug);
  const active = selected.some((choice) => choice.key === key);
  const limitReached = !active && selected.length >= 3;

  function toggle() {
    const current = parseChoices(
      sessionStorage.getItem(storageKey(procedureSlug)) ?? "[]",
    );
    const currentlyActive = current.some((choice) => choice.key === key);
    const next = currentlyActive
      ? current.filter((choice) => choice.key !== key)
      : current.length < 3
        ? [...current, { key, facilityId, locationId, name }]
        : current;
    sessionStorage.setItem(storageKey(procedureSlug), JSON.stringify(next));
    window.dispatchEvent(new Event("carevero:selection"));
  }

  return (
    <div className="compare-actions">
      <button
        type="button"
        className="button secondary"
        onClick={toggle}
        disabled={limitReached}
        aria-pressed={active}
        aria-label={`${active ? "Remove" : "Add"} ${name} ${active ? "from" : "to"} comparison`}
      >
        {active
          ? "✓ Selected"
          : limitReached
            ? "3 selected — remove one to add"
            : "+ Compare"}
      </button>
    </div>
  );
}

export function CompareTray({
  procedureSlug,
  payer,
}: {
  procedureSlug: string;
  payer?: string;
}) {
  const selected = useChoices(procedureSlug);

  if (selected.length === 0) return null;
  const compareQuery = new URLSearchParams({
    items: selected.map((choice) => choice.key).join(","),
    procedure: procedureSlug,
  });
  if (payer) compareQuery.set("payer", payer);
  const compareHref = `/compare?${compareQuery}`;
  function clear() {
    sessionStorage.removeItem(storageKey(procedureSlug));
    window.dispatchEvent(new Event("carevero:selection"));
  }
  return (
    <aside className="compare-tray" aria-live="polite">
      <div>
        <strong>Compare hospitals · {selected.length} of 3 selected</strong>
        <ul aria-label="Selected locations">
          {selected.map((choice) => (
            <li key={choice.key}>{choice.name}</li>
          ))}
        </ul>
      </div>
      <button className="text-button" type="button" onClick={clear}>
        Clear
      </button>
      {selected.length >= 2 ? (
        <Link className="button" href={compareHref}>
          Compare now <span aria-hidden="true">→</span>
        </Link>
      ) : (
        <span className="muted">Choose one more to compare</span>
      )}
    </aside>
  );
}
