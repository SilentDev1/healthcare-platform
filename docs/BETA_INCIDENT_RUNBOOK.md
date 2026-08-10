# Beta incident runbook

1. Assign incident lead, timestamp, severity, affected service/data, current SHA/revision,
   and correlation IDs. Preserve logs and provenance; do not collect patient information.
2. Contain: roll back a bad revision, pause scheduler/runaway import, disable public
   pricing for a data incident, revoke exposed credentials, or isolate a corrupt source.
3. Diagnose with safe logs, `/health`, `/ready`, Cloud SQL operations, job history,
   storage object checksum, and import/source records.
4. Recover using a known-good revision, forward schema fix, resumable import, clean
   source reprocessing, or isolated verified database restore.
5. Verify smoke/data invariants, monitor for recurrence, notify beta users when material,
   and record root cause/actions.

| Incident                          | Immediate action                                                                          |
| --------------------------------- | ----------------------------------------------------------------------------------------- |
| Incorrect price/source corruption | Disable affected publication or global pricing; trace provenance and verify official file |
| Site/API outage or high 5xx       | Check readiness/dependencies; roll back revision if deployment-related                    |
| Database outage                   | Fail readiness; stop migrations/imports; use Cloud SQL recovery, never static fixtures    |
| Bad deployment                    | Route traffic to prior web/API revisions                                                  |
| Bad migration                     | Stop rollout; prefer forward fix; restore only to isolated target with approval           |
| Credential exposure               | Revoke/rotate, inspect access logs, redeploy, assess scope                                |
| Runaway/repeated import           | Pause scheduler/job, preserve checkpoint, inspect bounds/lock and DB pressure             |
| Storage issue                     | Stop downloads; protect existing objects/version history; restore access/capacity         |

Escalate data-accuracy incidents to the product/data owner and security/credential events
to the cloud project owner. Legal notification decisions require the human owner.
