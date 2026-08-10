# Beta deployment runbook

This runbook is preparation only until Phase 4.6 is authorized. Never run `terraform
apply`, alter DNS, or enable traffic from Phase 4.5.

## Release sequence

1. Confirm `main` is clean, synchronized, reviewed, and no import is active.
2. Select an immutable Git SHA and run the manual **Beta release gate** workflow.
3. Run all Python/TypeScript checks, dependency and secret scans, migrations-from-zero,
   container builds, Terraform validation, and environment validation.
4. Build images tagged by SHA and record digests; never bake secrets into images.
5. Verify Secret Manager identifiers, service identities, Cloud SQL socket, source
   bucket, CORS, trusted hosts, beta noindex, feedback address, and pricing switch.
6. Confirm the latest managed backup is successful; create a manual pre-deploy backup
   before schema changes and record its ID.
7. Run the dedicated migration job/command: `python -m scripts.migrate_deployment`.
   Any failure stops rollout. Verify Alembic head and run `scripts.beta_data_smoke`.
8. Deploy a new API revision with no traffic. Verify `/version`, `/health`, `/ready`,
   correlation IDs, security headers, rate limiting, and admin-route 404 behavior.
9. Deploy a new web revision with no traffic. Run `scripts.beta_smoke` against revision
   URLs, including priced/no-price/multi-location facilities, compare, map, sources,
   Privacy, and Terms.
10. Verify Cloud Monitoring, logs, error visibility, budget alerts, scheduler paused
    state, and current source freshness.
11. Move a small traffic percentage, observe errors/latency/DB connections, then move
    beta traffic. Re-run smoke and data invariants.
12. Enable the scheduler only after a manual isolated refresh succeeds. Verify logs and
    the next run. Record SHA, image digests, revision names, migration head, backup ID,
    smoke output, and approver.

## Rollback

Move web and API traffic to their previous known-good Cloud Run revisions. Do not
automatically downgrade the database or delete newer data. Alembic migrations should be
forward-compatible; if an old application cannot use the new schema, keep the new API
revision and issue a forward fix. A database restore is an incident operation requiring
the recorded pre-migration backup, an isolated restore target, provenance checks, and
explicit owner approval.

Private beta permits a brief low-traffic maintenance window. Never deploy during a
major import. If pricing integrity is uncertain, set `PUBLIC_PRICING_ENABLED=false`
and deploy/revise configuration; explanatory and methodology pages remain available.
