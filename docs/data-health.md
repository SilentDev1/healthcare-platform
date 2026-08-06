# Data health

`make evaluate-data-health` seeds 14 governed rules, replaces the current evaluation snapshot,
calculates facility component scores, and snapshots each importer. Completeness is the share of
required facility checks passed. Overall score is the equal-weight mean of completeness,
freshness, validity, and provenance; the exact components are stored in `details`.

The default source freshness window is 90 days and facility freshness window is 365 days.
Threshold changes are reviewed code/configuration changes; APIs cannot execute arbitrary rules.
Historical import/source evidence remains immutable even though recalculated health snapshots
are replaceable.
