# NPPES organization importer

`make import-nppes-organizations` performs a bounded NPI Registry API query for New Hampshire
organization records with a hospital taxonomy description. The offline fixture is run with
`--source-file data/fixtures/nppes_organizations.json`. Responses are size-bounded, checksummed,
archived, linked to an import run, and skipped when checksum and parser version are unchanged.

Only institutional taxonomy prefixes are processed. Exact deterministic matches add an
organization NPI, source alias, and immutable observation. All other records become identity
candidates. NPPES is self-reported enumeration data: an NPI does not establish licensing,
credentialing, Medicare participation, facility ownership, or quality.

For production-scale updates, use the official version-2 monthly file plus weekly increments;
the Phase 3 API mode is intentionally bounded and is not a complete national synchronization.
