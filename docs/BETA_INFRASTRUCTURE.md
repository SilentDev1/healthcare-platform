# Beta infrastructure and environment model

## Decision

Carevero's approved preparation target is Google Cloud: Cloud Run for the public
web and API, a separate Cloud Run Job for imports, Cloud SQL PostgreSQL 17,
private versioned Cloud Storage for source files, Secret Manager, Cloud Scheduler,
and Cloud Monitoring. The admin app is not deployed. This preserves the repository's
existing Cloud Run/GCS direction and avoids GKE, Pub/Sub, Dataflow, and BigQuery.

No resource exists until Phase 4.6 is explicitly authorized.

## Environments

| Environment | Data                                     | Configuration                          | Indexing                  |
| ----------- | ---------------------------------------- | -------------------------------------- | ------------------------- |
| local       | local PostgreSQL; fixtures permitted     | `.env`                                 | enabled for local testing |
| test        | isolated ephemeral DB                    | test runner                            | disabled/not hosted       |
| beta        | separate Cloud SQL; official inputs only | Secret Manager + Cloud Run env         | disabled by default       |
| production  | separate Cloud SQL/project recommended   | Secret Manager + protected environment | explicit owner decision   |

`APP_ENV` is mandatory and never inferred from a hostname. In beta/production,
startup rejects local databases, HTTP public URLs, wildcard CORS/hosts, fixture
download paths, absent durable storage, absent feedback destination when feedback
is enabled, or unprotected enabled admin APIs. See `.env.beta.example`.

## Capacity and cost guardrails

Assumption: tens to low hundreds of users/day, roughly 100,000 API requests/month,
11 currently priced facilities, and one conservative refresh job at a time.

| Service                             | Guardrail                                                     | Expected monthly range (USD) |
| ----------------------------------- | ------------------------------------------------------------- | ---------------------------: |
| Cloud Run web/API                   | 1 vCPU, 512 MiB/1 GiB, min 0, max 3                           |                        $0–15 |
| Cloud Run import job                | 2 vCPU, 4 GiB, one job, max retry 1                           |                        $5–25 |
| Cloud SQL                           | 1 vCPU, 3.75 GiB, 20 GiB SSD, zonal, 7 backups                |                       $45–75 |
| Cloud Storage                       | versioned private bucket; temporary objects expire at 30 days |                        $2–10 |
| Logging/monitoring/scheduler/egress | 14-day log target, bounded checks                             |                        $0–15 |
| **Expected beta total**             | excluding domain and unusual egress                           |                  **$52–140** |

Actual prices must be confirmed with the Google Cloud calculator at deployment.
Set billing-budget notifications at 50%, 80%, and 100% of the owner-approved budget;
alerts do not stop billing. Cloud Run maximum instances cap request-driven spend.

## Connections and storage

API max database connections are bounded to `(pool size 5 + overflow 2) × max 3`
= 21, plus migration/import operations. Import work uses a separate job, conservative
write concurrency, and a PostgreSQL advisory lock per state. Cloud SQL has no public
IPv4 address; workloads connect through the platform Cloud SQL socket and least-
privilege identities.

Raw keys use `hospital-prices/US/<STATE>/<source-id>/<date>/original.<ext>` today,
with checksum stored in metadata and the database. A later key version may add facility
and checksum segments without changing the database provenance model.
Objects are private and versioned. SHA-256, byte size, content type, source URL,
download time/version, and object URI remain in source metadata. Provenance objects
are retained; only abandoned `tmp/` objects expire automatically after 30 days.

Recommended retention: raw source versions 7 years pending legal review; import
metadata/provenance for database lifetime; temporary and inactive `.part` files 7
days after confirming no active checkpoint; application logs 14 days; security logs
30 days; automated backups 7 days plus a manual pre-migration backup retained 30 days.

## IAM and exposure

- web: Cloud Run execution only; no database/storage secret access
- API: Cloud SQL Client and access to only its database URL secret
- import job: Cloud SQL Client, source bucket object user, database secret
- scheduler: invoke only the refresh job
- migration operator/job: Cloud SQL Client, database secret, explicit human invocation
- admin: not publicly deployed; API admin routes disabled in beta. If operators need
  the existing UI, run it locally against an IAM-restricted internal API tunnel.

Public web/API allow unauthenticated invocation. The source bucket is non-public and
PostgreSQL has no open Internet listener. Managed domain mappings provide TLS and
HTTP-to-HTTPS redirection. Canonical apex vs `www` remains owner-configurable; redirect
the noncanonical hostname and use `PUBLIC_APP_URL` for canonical metadata.

## Monitoring

Create simple uptime checks for `/`, `/health`, `/ready`, and one bounded search.
Alert on two consecutive availability failures, API 5xx rate above 5% for five minutes,
database readiness failure, refresh job failure, repeated importer failure, source
freshness breach, and storage/budget thresholds. Log JSON request status, route,
latency, environment, service, and correlation ID. Search logs retain query length and
result count, not identifiable query/IP histories. Cloud Error Reporting is sufficient;
do not add a third-party SDK for beta.

No invasive consumer analytics is configured. Future privacy-preserving metrics may
aggregate search, procedure, facility, and compare counts without user profiles.
