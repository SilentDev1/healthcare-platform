# Hospital price transparency

Phase 4 ingests public hospital machine-readable files (MRFs) for New Hampshire. It does not ingest insurer Transparency in Coverage files, claims, member data, or PHI. Sources must be an official hospital domain or an MRF host explicitly linked by that hospital. The collector never bypasses access controls.

Supported inputs are CMS-style and reviewed legacy CSV/JSON plus NDJSON, ZIP, and GZIP containers. Unknown layouts are retained in the parser review queue and are never published. Federal requirements evolve; operators should compare the parser registry with the current [CMS Hospital Price Transparency resources](https://www.cms.gov/priorities/key-initiatives/hospital-price-transparency/resources) before approving a new schema.

Raw files and metadata are retained by source and date under `data/raw/hospital_prices/nh`. Checksums make unchanged reruns idempotent; historical files are never overwritten.
