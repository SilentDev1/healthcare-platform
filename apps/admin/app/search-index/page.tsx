export default function SearchIndex() {
  return (
    <main>
      <p className="eyebrow">INTERNAL ONLY</p>
      <h1>Search index status</h1>
      <p>
        The PostgreSQL index is rebuilt with{" "}
        <code>make rebuild-search-index</code>. The search testing page confirms
        ranked output and explanations.
      </p>
    </main>
  );
}
