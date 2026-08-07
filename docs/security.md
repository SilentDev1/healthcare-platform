# Security

Hospital pricing contains no PHI, claims, member identifiers, or individualized benefits. Downloads enforce scheme, redirect, timeout, content-type, byte, archive-entry, traversal, and expanded-size bounds. Unknown schemas quarantine. Numeric values are never AI-modified.

CareCompare handles public facility information only. PHI, patient data, member identifiers,
medical records, and free-form clinical information are prohibited. If such data is observed,
stop ingestion and follow the incident process before retaining or processing it.

- Secrets belong in local environment variables or an approved secret manager, never Git.
- SQLAlchemy binds query parameters; do not construct SQL with user input.
- FastAPI/Pydantic validates identifiers, pagination, and two-character state filters.
- HTTP collection uses timeouts, limited retries, redirects, allowlisted content types,
  streamed reads, and both declared and actual file-size limits.
- Phase 1 does not extract archives. A later archive importer must reject absolute paths,
  traversal (`..`), links, excessive file counts, and excessive expanded size.
- Dependencies are exactly pinned and lockfiles are committed.
- Logs are structured and must not include secrets or prohibited data.
- Imported records require URL, checksum, source/import timestamps, and parser version.

Production hardening will add authentication for admin surfaces, least-privilege service
accounts, TLS-only endpoints, vulnerability scanning, and retention controls before launch.
