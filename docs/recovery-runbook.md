# Local logical recovery runbook

This authored runbook covers the fictional local portal. It is not evidence that an infrastructure
outage was recovered. Policies POL-06 and POL-07 define the exercise's 30-minute RTO and 24-hour RPO.

1. The project owner declares the exercise, identifies the source project/database and records the
   start time. Keep the source available. Confirm Docker, the app image, PostgreSQL, free disk space
   and access to the restricted runtime backup volume.
2. Stop if the backup is missing, corrupt, incompatible or lacks its recorded SHA-256. Never rename
   a failed backup as successful. Preserve the failure, its run ID and original artifact.
3. Create a distinctly named empty restore database. Never use the source database or a populated
   target. The restore command rejects populated business tables before changing data.
4. Restore all canonical business tables in dependency order. Compare restored rows and counts
   against the validated backup, normalizing datetime representation rather than ignoring values.
5. Perform read-only portal acceptance against the restored database and reconcile the request IDs.
   Do not switch the live portal to the restore target as part of this bounded exercise.
6. Record the declared logical outage, successful acceptance time and latest recoverable committed
   business timestamp. Calculate RTO and RPO from those timestamps. Generated history is unsuitable
   for the latest real recoverable checkpoint.
7. If any comparison or acceptance fails, stop and retain the isolated target and failure record.
   The intact source is the fallback. Investigate before another attempt; do not delete source data.
8. Retain sanitized observations, backup hash, result and limitations. Keep raw backups and secrets in
   ignored restricted runtime storage. The owner reviews findings, lessons and any follow-up action.
   Explicitly identify retained restore databases and scenario volumes before later scoped cleanup.

The automated verifier in [verify-runtime.py](../scripts/lab/verify-runtime.py) implements the logical
exercise and adds one labelled synthetic checkpoint to the source. Each invocation adds a checkpoint
and retains a restore database; repeated runs are therefore deliberate state changes.

The 11 October 2026 exercise restored 51 requests and passed read-only API acceptance in approximately
0.36 seconds, with approximately 0.59 seconds of measured RPO. These values describe that single run
on the local machine and do not establish sustained service targets or full disaster recovery.
