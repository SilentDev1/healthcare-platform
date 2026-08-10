# Beta operations runbook

## Daily operation

- Check web, API health/readiness, 5xx rate, DB connections, refresh result, source
  freshness, official-source coverage, and budget trend.
- Daily refresh checks metadata/change signals first. Changed sources download to a
  temporary object, verify bounds and checksum, then parse/normalize/map/validate and
  rebuild affected summaries. Weekly perform deeper link rediscovery; monthly run the
  statewide data-health audit.
- The scheduler calls `python -m scripts.run_price_refresh --state NH`. `STATE` is a
  parameter, not an architectural constant. The PostgreSQL advisory lock prevents
  overlapping state jobs. Pause the Cloud Scheduler job or set
  `SCHEDULER_ENABLED=false` during incidents.
- A failed new source does not delete previous publishable summaries. Preserve the
  failure/import record and checkpoint, investigate, resume where safe, and show stale
  data under existing freshness policy.

## Health, restart, and outages

- `/health` proves process liveness. `/ready` proves database availability; it does not
  call hospital sources. `/version` identifies the build without secrets.
- Restart by creating/restarting a Cloud Run revision/job; do not mutate containers.
- Web/API outage: verify revision, logs, readiness, Cloud SQL, secrets, IAM, and DNS/TLS;
  roll traffic back if deployment-related.
- Database outage: readiness must fail and the web must show a safe error—never fixture
  data. Check Cloud SQL operations and connections; do not expose a public DB port.
- Source outage: keep last valid data, record failure, attempt official rediscovery, and
  suppress only when publication safety requires it.

## Backup and restore

Cloud SQL automated backup and point-in-time recovery are enabled with seven retained
backups. Before migration, create and record an on-demand backup. Quarterly, restore the
latest backup to a new isolated instance/database, run Alembic head plus
`scripts.beta_data_smoke`, compare counts/checksums/provenance, then delete the isolated
test only after approval. Never test restore over beta/production.

Local rehearsal:

```bash
docker compose exec -T postgres pg_dump -U carecompare -Fc carecompare > /tmp/carevero.dump
createdb carevero_restore_test
pg_restore --no-owner --dbname carevero_restore_test /tmp/carevero.dump
DATABASE_URL=postgresql+psycopg://.../carevero_restore_test python -m scripts.beta_data_smoke
dropdb carevero_restore_test
```

Validate the explicit database target before creation/drop. Dumps are temporary,
restricted, uncommitted, and securely removed after verification.

## Incorrect-price escalation

Record the page URL, facility/location, procedure, displayed amount, and report time—no
patient details. Trace summary → mapping → record → import → source/checksum. Compare the
current official file. If materially unsafe, suppress the affected publication state or
disable public pricing globally; never delete provenance. Fix deterministic parser/mapping,
reprocess, validate, republish, and document resolution.

## Secrets and emergency controls

Rotate by adding a new Secret Manager version, deploying a revision that uses it,
verifying, then disabling the old version. For exposure, revoke first and follow the
incident runbook. Emergency controls are `PUBLIC_PRICING_ENABLED=false`, paused scheduler,
Cloud Run traffic rollback, and—only if necessary—zero public web traffic. They do not
delete data. Admin remains local/IAM-restricted and always noindex.

Massachusetts requires no architecture change: add official data/scheduler scope and
increase storage/compute/DB capacity within measured limits.
