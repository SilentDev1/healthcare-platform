# Search platform

`make rebuild-search-index` creates one document per active facility, procedure, and category.
Ranking is stable: exact primary text, exact alias, prefix/phrase, then conservative typo
similarity. Filters are bounded by entity, geography, and category. Each result explains its
match. PostgreSQL provides GIN full-text and `pg_trgm` indexes; no external search service is
required. Incremental writers may rebuild the affected entity, while the Phase 3 commands use a
transactional full rebuild.

Limitations: typo comparison is deliberately conservative, abbreviations require aliases, and
ranking is not a clinical recommendation. Search logs store query length, timing, and result
count—not query text or user identifiers.

Run `uv run python -m scripts.benchmark_search` for the representative local six-query set.
Record median, p95, database size, and hardware context in the verification report; these local
figures are diagnostic rather than a production service-level objective.
