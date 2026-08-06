# Data provenance

Every imported facility references a `source_files` row containing the official source URL,
download timestamp, source publication timestamp when available, SHA-256 checksum, HTTP
metadata, file size, storage path, and parser version. Each execution also creates an
`import_runs` row with start/end times, outcome, row counts, and a bounded error summary.

Raw files are immutable inputs. They are written under ignored `data/raw/` locally and should
move to versioned Google Cloud Storage only after cloud infrastructure is approved. Fixture
files are synthetic and may be committed. Rejected rows are written to ignored JSON Lines
files with their row number and reason.

Normalization may trim strings, standardize state codes, and map source columns. It must not
infer, interpolate, round, or otherwise modify healthcare prices. AI may propose mappings,
but deterministic reviewed code performs imports. Reprocessing a checksum with a new parser
version creates a new source/import audit record and updates each facility's current source
link; historical import records remain intact.

## Phase 2 recommendation: multi-source matching

The Phase 1 mandatory `facilities.source_file_id` is acceptable while a facility is defined by
one authoritative CMS feed: it identifies the source snapshot that most recently updated the
canonical row. It should not become the long-term multi-source provenance model. A single
foreign key cannot represent multiple supporting or conflicting source observations and would
force matching logic to overwrite earlier lineage.

Before adding a second facility source in Phase 2, introduce source-specific observation rows
(for example, `facility_source_records`) keyed to both the canonical facility and source file.
Keep raw source identifiers and normalized values on those immutable observations, record the
match method and confidence separately, and make canonical-field derivations traceable to one
or more observations. At that point, deprecate or redefine `facilities.source_file_id` as a
clearly named latest-primary-source pointer; do not use it as the complete provenance history.
