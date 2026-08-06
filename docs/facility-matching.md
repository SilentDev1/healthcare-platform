# Facility matching

Quality records match facilities only when their supplied CMS Certification Number exactly
equals `facilities.cms_certification_number`. Whitespace is trimmed; names are not used for
automatic matching. Similar-name or fuzzy matching is prohibited for unattended imports.

When no exact CCN exists, the complete source payload is stored in
`unmatched_source_records` with source/import IDs, supplied CCN/name, reason, pending review
status, and review placeholders. Phase 2 exposes this queue read-only. A later authenticated
workflow may record a reviewer and resolution, but must never silently merge facilities.
