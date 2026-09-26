# Generator–evaluator quality harness

This directory adapts ECC's GAN-style harness to an assessment-heavy backend project. It is a review
contract, not an autonomous release mechanism: the generator implements a bounded slice; a separate
evaluator tests the live behavior and evidence; the generator addresses findings; the owner decides
whether release gates are met.

- [Specification](SPEC.md)
- [Evaluation rubric](EVALUATION_RUBRIC.md)

The evaluator never edits implementation or assessment conclusions. A pass score cannot override a
release blocker, missing manual review, or publication approval.
