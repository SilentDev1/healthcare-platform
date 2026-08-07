# Pricing anomaly governance

Versioned deterministic rules flag malformed values, inconsistent ranges, duplicates, missing payer names, suspicious zeros, schema weakness, source changes, staleness, and coverage failures. Anomalies explain the rule, severity, source record, and details. They never alter a source value.

Errors and critical anomalies block publication. Reviewers may resolve or suppress a projection with an audit entry, but cannot erase raw observations. Recalculate anomalies after a parser or mapping change and retain previous source versions.
