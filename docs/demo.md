# Demonstration guide

## Purpose

The demonstration shows traceability and control behavior, not a polished fiction. Use an actual run
ID and the evidence generated in that run. Never reuse the illustrative IDs below as if observed.

## Prepare

```powershell
./scripts/demo.ps1 -Scenario S01 -Seed 42 -KeepRunning
```

The wrapper runs both environment and application diagnostics, starts the contained lab, seeds the
deterministic population, and runs the selected baseline scenario. Keep the printed run ID. If a step
fails, stop and record the real limitation instead of continuing with staged output.

## Ten-minute sequence

1. **Context and boundary (1 minute).** Show the persistent simulation banner, local URL, current
   scenario/run ID, and synthetic-data label. State that the builder is also the assessor.
2. **Secure-default control (2 minutes).** Attempt a privileged action with a password-only or wrong-
   role session. Show the server-side denial and unchanged data, not only a hidden button.
3. **Finding/evidence chain (3 minutes).** Open one S01 workpaper. Follow criteria, selected user,
   observed retained leaver access, evidence ID/hash, design and operating conclusions, and finding.
4. **Remediation/retest (2 minutes).** Using the actual baseline ID, run:

   ```powershell
   uv run python -m cyber_assess scenario remediate --id S01 --baseline-run RUN_FROM_OUTPUT
   uv run python -m cyber_assess scenario retest --id S01 --baseline-run RUN_FROM_OUTPUT
   ```

   Show that deactivation blocks new login and invalidates an existing session. Preserve the baseline
   failure and show the fresh retest ID.
5. **Recovery and reporting (1 minute).** Show one isolated restoration result with measured timestamps
   and follow one report reference back to its control workpaper/evidence index.
6. **Limitations (1 minute).** State unresolved findings, selected-only RMiT coverage, self-review, and
   the difference between fixture history and actual execution.

## Five-minute discussion

- Why opaque server-side sessions were chosen: deactivation and role changes can revoke them.
- Why PostgreSQL is not host-published: local containment and a narrower attack surface.
- Why a technically passing script cannot set the conclusion: evidence still requires human judgment.
- Why baseline evidence is immutable: remediation must not erase the condition that supported the
  finding.
- What would change for production: external identity, TLS, independent assurance, enterprise logging,
  managed secrets, availability engineering, and organization-specific legal/regulatory analysis.

## Finish

```powershell
uv run python -m cyber_assess lab stop
```

Stopping preserves project data. Do not run broad Docker prune or volume deletion commands as part of
the demonstration.
