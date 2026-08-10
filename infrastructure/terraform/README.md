# Carevero Google Cloud beta infrastructure

This Terraform describes—but does not create—the approved Phase 4.5 target:
Cloud Run web/API, a separately sized Cloud Run refresh job, Cloud SQL
PostgreSQL 17 with no authorized public networks, a non-public versioned source
bucket, Secret Manager references, Cloud Scheduler, service identities, and
budget-conscious scaling.

The backend uses the existing private, versioned state bucket in project
`carecompare-development`. Never commit state or a plan file. Review every plan
for unrelated changes or destroys before applying it.

```bash
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
terraform plan -refresh=false -var='project_id=PROJECT' \
  -var='web_image=IMAGE@DIGEST' -var='api_image=IMAGE@DIGEST' \
  -var='job_image=IMAGE@DIGEST'
```

Secret Manager must contain a version of `carevero-beta-database-url` before the
Cloud Run workloads are applied. Values are never Terraform variables. The admin
Next.js app is intentionally absent, and the beta public API returns 404 for admin
routes.

The approved private-beta budget is $100/month. Build application images with the
checked-in Cloud Build configurations under `infrastructure/cloudbuild/` and use
immutable Git SHA tags.
