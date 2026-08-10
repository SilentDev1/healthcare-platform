"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface CompareChoice {
  key: string;
  facilityId: string;
  locationId: string;
  name: string;
}

function readChoices(): CompareChoice[] {
  if (typeof window === "undefined") return [];
  try {
    const value: unknown = JSON.parse(
      sessionStorage.getItem("careveroCompareV1") ?? "[]",
    );
    return Array.isArray(value) ? (value as CompareChoice[]).slice(0, 3) : [];
  } catch {
    return [];
  }
}

export function CompareSelect({
  facilityId,
  locationId,
  name,
}: {
  facilityId: string;
  locationId: string;
  name: string;
}) {
  const key = `${facilityId}~${locationId}`;
  const [selected, setSelected] = useState<CompareChoice[]>(readChoices);
  const active = selected.some((choice) => choice.key === key);

  useEffect(() => {
    function synchronize() {
      setSelected(readChoices());
    }
    window.addEventListener("carevero:selection", synchronize);
    return () => window.removeEventListener("carevero:selection", synchronize);
  }, []);

  function toggle() {
    const current = readChoices();
    const currentlyActive = current.some((choice) => choice.key === key);
    const next = currentlyActive
      ? current.filter((choice) => choice.key !== key)
      : current.length < 3
        ? [...current, { key, facilityId, locationId, name }]
        : current;
    setSelected(next);
    sessionStorage.setItem("careveroCompareV1", JSON.stringify(next));
    window.dispatchEvent(new Event("carevero:selection"));
  }

  return (
    <div className="compare-actions">
      <button
        type="button"
        className="button secondary"
        onClick={toggle}
        aria-pressed={active}
        aria-label={`${active ? "Remove" : "Add"} ${name} ${active ? "from" : "to"} comparison`}
      >
        {active ? "✓ Selected" : "+ Compare"}
      </button>
    </div>
  );
}

export function CompareTray({ procedureSlug }: { procedureSlug: string }) {
  const [selected, setSelected] = useState<CompareChoice[]>(readChoices);

  useEffect(() => {
    function synchronize() {
      setSelected(readChoices());
    }
    window.addEventListener("carevero:selection", synchronize);
    return () => window.removeEventListener("carevero:selection", synchronize);
  }, []);

  if (selected.length === 0) return null;
  const compareHref = `/compare?items=${selected.map((choice) => choice.key).join(",")}&procedure=${encodeURIComponent(procedureSlug)}`;
  return (
    <aside className="compare-tray" aria-live="polite">
      <div>
        <strong>
          {selected.length} location{selected.length === 1 ? "" : "s"} selected
        </strong>
        <span>Select up to 3 locations.</span>
      </div>
      {selected.length >= 2 ? (
        <Link className="button" href={compareHref}>
          Compare {selected.length}
        </Link>
      ) : (
        <span className="muted">Choose one more to compare</span>
      )}
    </aside>
  );
}
