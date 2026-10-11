# Evaluation rubric

Score each dimension from 1–10 using direct evidence. Weighted score is the sum of score × weight. The
pass threshold is **8.0**, with no score below 7 and no mandatory blocker.

| Dimension | Weight | 1–3 | 4–6 | 7–8 | 9–10 |
| --- | ---: | --- | --- | --- | --- |
| Security and containment | 30% | Secure default broken, secret exposed, broad target | Happy path protected but abuse paths or isolation incomplete | Authorization, sessions, CSRF, throttling, scenario scope, and network defaults verified | Strong negative/failure coverage plus independently reproduced containment |
| Evidence integrity and assessment quality | 25% | Fabricated/mutable/untraceable evidence or unsupported conclusion | Structured records exist but lineage, conflicts, or limitations are weak | Hashes, provenance, design/operation conclusions, immutable baselines, and fresh retests reconcile | Adversarial tamper/interruption tests pass and judgment is exceptionally transparent |
| Functional correctness | 20% | Core journey/CLI broken | Happy path works; required edges fail | Required behavior and safe error contracts pass | Complete AT behavior with deterministic recovery from injected failures |
| Reproducibility and operations | 15% | Unlocked/unbounded/manual-only | Setup works only in one existing environment | Locked Windows/Linux paths, healthy contained stack, deterministic seed/export | Fresh reproductions meet measured startup/export/capacity targets with clear diagnostics |
| Documentation and claim honesty | 10% | Misleading real-client/compliance claim or missing handoff | Basic docs exist but commands/limits drift | Docs match implementation, sources/claims are gated, links resolve | A new reviewer reproduces a full chain and every published claim resolves to final evidence |

## Mandatory blockers

Regardless of weighted score, fail the iteration for: secure-default authorization bypass; leaked
credential or prohibited data; database host exposure; unsafe scenario scope/cleanup; untraceable
material finding; changed/missing evidence accepted as valid; false or backdated evidence; regulatory
claim from an unverified mapping; failed required AT; missing required DEL artifact; or a generated
bundle containing raw secrets/backups/unsafe links.

## Evaluator output

```text
Revision / snapshot / run IDs:
Environment and actual UTC interval:
Commands and interfaces exercised:
Scores with cited evidence:
Blockers:
Major findings:
Minor findings:
Requirements not exercised:
Regression checks:
Weighted score and verdict: PASS | ITERATE | STOP FOR OWNER
```

Praise is not evidence. The evaluator cites exact test output, records, endpoints, hashes, screenshots
with context, or manual inspection notes. Any unexercised requirement remains unverified.
