# Data provenance

Hospital price records reference an immutable source file and import run and retain a source record identifier or line number, raw payload and hash, parser name/version, observation time, source URL, checksum, and facility source observation when applicable. Versions are retained; an unchanged checksum skips normalization instead of overwriting history.

Phase 3 sources follow the existing chain: `source_files` records URL, archive path, checksum,
size, parser version, and timestamps; `import_runs` records processing outcomes; immutable
observations retain source records. Facility identifiers and aliases may additionally point to
their source file and observation. Identity candidates retain raw payloads and decisions append
review evidence. A nullable source pointer on the canonical facility is only a compatibility
convenience and must not be interpreted as exclusive ownership by one source.

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

## Multi-source facility and quality observations

The Phase 1 mandatory `facilities.source_file_id` is acceptable while a facility is defined by
one authoritative CMS feed: it identifies the source snapshot that most recently updated the
canonical row. It should not become the long-term multi-source provenance model. A single
foreign key cannot represent multiple supporting or conflicting source observations and would
force matching logic to overwrite earlier lineage.

Phase 2 therefore adds `facility_source_observations`, keyed to canonical facility, source
file, import run, and source record identifier. Raw payloads and hashes are immutable.
`facility_quality_measure_observations` retain CMS values and reporting context separately
from consumer-facing measure names and directionality. `facilities.source_file_id` remains the
latest-primary-source pointer and is not treated as the complete provenance history.

Consumer summaries may select the most recent reporting period and explain directionality,
but raw observations are never overwritten or converted into invented ratings. Footnote codes
remain attached to the observation and indicate CMS suppression or qualification; clients
must display “Not available” rather than deriving a value when CMS withholds one.
