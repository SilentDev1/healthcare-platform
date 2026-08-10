"use client";

import Link from "next/link";

export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <main className="narrow state-page">
      <p className="eyebrow">Temporary problem</p>
      <h1>Carevero couldn’t load this page</h1>
      <p>
        No prices have been estimated or filled in. Try again or start over.
      </p>
      <div className="card-actions">
        <button className="button" type="button" onClick={reset}>
          Try again
        </button>
        <Link className="button secondary" href="/">
          Return home
        </Link>
      </div>
    </main>
  );
}
