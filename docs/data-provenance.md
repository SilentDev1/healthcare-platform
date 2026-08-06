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
