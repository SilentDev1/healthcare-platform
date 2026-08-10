import Link from "next/link";

export default function NotFound() {
  return (
    <main className="narrow state-page">
      <p className="eyebrow">Page not found</p>
      <h1>We couldn’t find that Carevero page</h1>
      <p>
        The link may be outdated. Search for care or browse the current hospital
        and procedure directories.
      </p>
      <div className="card-actions">
        <Link className="button" href="/search">
          Search Carevero
        </Link>
        <Link className="button secondary" href="/hospitals">
          Browse hospitals
        </Link>
        <Link className="button secondary" href="/procedures">
          Browse procedures
        </Link>
      </div>
    </main>
  );
}
