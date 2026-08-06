# Facility identity

Identity matching is deterministic and explainable. Precedence is exact CMS CCN, exact
organization NPI, exact trusted source identifier, normalized legal/alias name plus address,
then normalized legal/alias name plus phone. Name-only and fuzzy similarity never auto-merge;
they create immutable, reviewable candidates. Decisions append to the audit trail and are not
deleted.

`make seed-facility-identity` backfills CMS CCNs as strong identifiers and applies the tiny,
code-reviewed system alias list. Curated aliases retain the facility's CMS source pointer and
must be reviewed like any other identity assertion.

Names use Unicode folding, lowercase alphanumerics, whitespace normalization, and common
corporate-suffix removal. Addresses normalize common street words; phones retain ten digits;
postal codes retain the first five characters; domains remove scheme and `www`. Address hashes
are SHA-256 over normalized address, city, state, and postal code.

Supported identifiers are CMS CCN, organization/individual NPI, irreversible TIN hash, state
license, internal source ID, domain, phone, and address hash. Raw TINs are prohibited. To add a
source, archive it in `source_files`, create an `import_run`, store observations, apply this
precedence, and create a candidate whenever the evidence is not exact.
