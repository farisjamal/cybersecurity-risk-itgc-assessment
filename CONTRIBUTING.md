# Contributing

This portfolio is intentionally maintained as a sole-author project. External pull requests are not
accepted at this stage so authorship and assessment provenance remain unambiguous. Suggestions may be
raised as issues without implying contributor or reviewer status.

Owner changes follow this workflow:

1. Open an issue referencing PRD requirement and acceptance-test identifiers.
2. Create a focused branch from the current default branch.
3. Implement the smallest complete change with tests and documentation.
4. Run `./scripts/quality/check-repository.ps1` and the relevant integration checks.
5. Open a pull request using the repository template and complete a self-review.
6. Merge only after required checks pass; release and publication are separate decisions.

Do not add co-author trailers, fabricated approvals, backdated evidence, real client information, or
generated secrets. Automated tools may assist the owner but must not be represented as contributors.
