"use client";
import Link from "next/link";
import { useState } from "react";
export function CompareSelect({ id, name }: { id: string; name: string }) {
  const [selected, setSelected] = useState<string[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      return JSON.parse(sessionStorage.getItem("compareFacilities") ?? "[]");
    } catch {
      return [];
    }
  });
  const active = selected.includes(id);
  function toggle() {
    const next = active
      ? selected.filter((x) => x !== id)
      : selected.length < 3
        ? [...selected, id]
        : selected;
    setSelected(next);
    sessionStorage.setItem("compareFacilities", JSON.stringify(next));
  }
  return (
    <>
      <button
        type="button"
        className="button secondary"
        onClick={toggle}
        aria-pressed={active}
        aria-label={`${active ? "Remove" : "Add"} ${name} ${active ? "from" : "to"} comparison`}
      >
        {active ? "✓ Selected" : "+ Compare"}
      </button>
      {selected.length >= 2 && (
        <Link className="button" href={`/compare?ids=${selected.join(",")}`}>
          Compare {selected.length}
        </Link>
      )}
      {!active && selected.length === 3 && (
        <span className="muted" role="status">
          3 facility limit
        </span>
      )}
    </>
  );
}
