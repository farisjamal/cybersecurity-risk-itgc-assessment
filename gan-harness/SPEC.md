# Harness specification

## Objective

Iteratively deliver the PRD while preserving secure defaults, evidence integrity, reproducibility, and
honest portfolio boundaries. The complete product is evaluated against AT-01–AT-20 and DEL-01–DEL-10;
each iteration handles a smaller contract.

## Roles

### Planner

- Selects one vertical slice with explicit FR/NFR/AT/DEL identifiers.
- Defines expected positive, negative, failure, integrity, and cleanup behavior.
- Identifies evidence that must be generated and evidence that must remain immutable.
- Refuses scope reductions that would silently change the PRD; material changes require an ADR.

### Generator

- Owns only the files named in the iteration contract.
- Implements the smallest complete behavior and tests from the locked environment.
- Never weakens secure defaults to make a scenario or test pass.
- Records actual commands/results and distinguishes synthetic history from observed execution.
- Does not commit, publish, merge, or mark claims verified without owner authorization.

### Evaluator

- Starts from a clean, project-scoped environment and tests the live interface plus canonical records.
- Uses direct HTTP/API tests for authorization, not only page visibility.
- Challenges evidence completeness, hashes, lineage, frozen-baseline behavior, and reconciliation.
- Reports defects with reproduction, requirement impact, expected/actual result, and severity.
- Does not propose and then grade its own fixes; the generator owns corrections.

## Iteration contract

Before implementation, record:

1. Requirement and acceptance IDs.
2. Owned files and out-of-scope files.
3. Required environment and synthetic fixtures.
4. User/API/CLI behavior and exit codes.
5. Security and evidence abuse cases.
6. Tests, evidence outputs, and cleanup expectations.
7. Documentation/claim changes.

## Loop

1. Planner freezes the iteration contract.
2. Generator implements and runs focused gates.
3. Evaluator independently runs the rubric and writes structured feedback.
4. Generator addresses every blocker/major issue or documents why the contract must change.
5. Evaluator retests from fresh state.
6. Stop on pass, maximum 10 iterations, or a three-iteration score plateau.

The default evaluation mode is code/API/CLI plus live browser interaction for user-visible flows. Do
not substitute screenshots for functional testing. Scenario projects and evidence IDs must be unique
per iteration; cleanup must not touch unrelated Docker resources or files.

## Mandatory stop conditions

- Any secret, real personal/client data, unsafe external target, or broad destructive command.
- Broken authentication/authorization in secure mode.
- Mutable baseline evidence, invalid hashes, or apparently final partial export.
- Unverified regulatory claim, fabricated review, or completed-work claim without final evidence.
- Missing mandatory deliverable or failed AT requirement for the evaluated release.
