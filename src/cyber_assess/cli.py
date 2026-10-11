"""Command-line interface for assessment, integrity, and bounded lab workflows."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from cyber_assess.adapters import route_scenario, run_compose, seed_lab
from cyber_assess.artifacts import create_final_artifacts
from cyber_assess.bootstrap import initialize_engagement
from cyber_assess.dependency_audit import audit_dependencies
from cyber_assess.doctor import run_doctor
from cyber_assess.errors import AssessmentError, IntegrityError, InvalidInputError
from cyber_assess.readiness import release_readiness
from cyber_assess.reporting import create_deliverable_inputs
from cyber_assess.snapshots import create_sanitized_export, create_snapshot, verify_snapshot
from cyber_assess.validation import validate_assessment, validate_findings

EXIT_EXECUTION_FAILURE = 1
EXIT_INVALID_INPUT = 2
EXIT_MISSING_PREREQUISITE = 3
EXIT_INTEGRITY_FAILURE = 4


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="json_output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cyber_assess")
    subcommands = parser.add_subparsers(dest="command", required=True)

    doctor = subcommands.add_parser("doctor", help="check local prerequisites without secrets")
    _add_json(doctor)

    readiness = subcommands.add_parser(
        "release-check", help="check recorded final release criteria"
    )
    readiness.add_argument("--engagement", required=True)
    _add_json(readiness)
    dependencies = subcommands.add_parser("dependencies")
    dependency_commands = dependencies.add_subparsers(dest="dependency_action", required=True)
    _add_json(dependency_commands.add_parser("audit"))

    init = subcommands.add_parser("init", help="initialize canonical assessment records")
    init.add_argument("--engagement", required=True)
    init.add_argument("--workspace", type=Path)
    _add_json(init)

    lab = subcommands.add_parser("lab", help="operate the fixed local Compose project")
    lab_commands = lab.add_subparsers(dest="lab_action", required=True)
    for action in ("up", "stop"):
        child = lab_commands.add_parser(action)
        _add_json(child)
    seed = lab_commands.add_parser("seed")
    seed.add_argument("--seed", type=int, default=42)
    _add_json(seed)

    scenario = subcommands.add_parser("scenario", help="run only allowlisted lab scenarios")
    scenario_commands = scenario.add_subparsers(dest="scenario_action", required=True)
    for action in ("run", "remediate", "retest"):
        child = scenario_commands.add_parser(action)
        child.add_argument("--id", required=True, dest="scenario_id")
        if action != "run":
            child.add_argument("--baseline-run", required=True)
        _add_json(child)

    assess = subcommands.add_parser("assess")
    assess_commands = assess.add_subparsers(dest="assess_action", required=True)
    assess_validate = assess_commands.add_parser("validate")
    assess_validate.add_argument("--engagement", required=True)
    _add_json(assess_validate)

    findings = subcommands.add_parser("findings")
    finding_commands = findings.add_subparsers(dest="findings_action", required=True)
    findings_validate = finding_commands.add_parser("validate")
    findings_validate.add_argument("--engagement", required=True)
    _add_json(findings_validate)

    snapshot = subcommands.add_parser("snapshot")
    snapshot_commands = snapshot.add_subparsers(dest="snapshot_action", required=True)
    snapshot_create = snapshot_commands.add_parser("create")
    snapshot_create.add_argument("--engagement", required=True)
    _add_json(snapshot_create)

    export = subcommands.add_parser("export")
    export.add_argument("--snapshot", required=True)
    export.add_argument("--format", choices=("all", "json", "manifest"), default="all")
    _add_json(export)

    report_inputs = subcommands.add_parser(
        "report-inputs",
        help="generate reconciled reporting inputs from a verified snapshot",
    )
    report_inputs.add_argument("--snapshot", required=True)
    _add_json(report_inputs)

    artifacts = subcommands.add_parser(
        "artifacts",
        help="render reconciled workbook, report, roadmap, and presentation artifacts",
    )
    artifacts.add_argument("--snapshot", required=True)
    _add_json(artifacts)

    verify = subcommands.add_parser("verify")
    verify.add_argument("--snapshot", required=True)
    _add_json(verify)
    return parser


def _emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return
    message = payload.get("message") or payload.get("status") or "completed"
    print(message)
    for key, value in payload.items():
        if key not in {"message", "status"}:
            print(f"{key}: {value}")


def _workspace(args: argparse.Namespace, default_workspace: Path | None) -> Path:
    explicit = getattr(args, "workspace", None)
    return (explicit or default_workspace or Path.cwd()).resolve()


def _dispatch(args: argparse.Namespace, workspace: Path) -> tuple[int, dict[str, Any]]:
    if args.command == "release-check":
        result = release_readiness(workspace, args.engagement)
        return (0 if result["ready"] else EXIT_INTEGRITY_FAILURE), result
    if args.command == "dependencies":
        result = audit_dependencies(workspace)
        return (0 if result["status"] == "clean" else EXIT_EXECUTION_FAILURE), result
    if args.command == "doctor":
        doctor_result = run_doctor(workspace)
        return (0 if doctor_result.ok else EXIT_MISSING_PREREQUISITE), doctor_result.as_dict()
    if args.command == "init":
        path = initialize_engagement(workspace, args.engagement)
        return 0, {"status": "initialized", "engagement": args.engagement, "path": str(path)}
    if args.command == "lab":
        if args.lab_action == "seed":
            return 0, seed_lab(workspace, args.seed)
        return 0, run_compose(workspace, args.lab_action)
    if args.command == "scenario":
        scenario_result = route_scenario(
            workspace,
            args.scenario_action,
            args.scenario_id,
            baseline_run_id=getattr(args, "baseline_run", None),
        )
        return 0, scenario_result
    if args.command == "assess":
        assessment_result = validate_assessment(workspace, args.engagement)
        return (0 if assessment_result.valid else EXIT_INVALID_INPUT), {
            "valid": assessment_result.valid,
            "errors": assessment_result.errors,
            "warnings": assessment_result.warnings,
            "validated_ids": assessment_result.validated_ids,
        }
    if args.command == "findings":
        findings_result = validate_findings(workspace, args.engagement)
        return (0 if findings_result.valid else EXIT_INVALID_INPUT), {
            "valid": findings_result.valid,
            "errors": findings_result.errors,
            "validated_ids": findings_result.validated_ids,
        }
    if args.command == "snapshot":
        snapshot = create_snapshot(workspace, args.engagement)
        return 0, {"status": "created", "snapshot_id": snapshot.id}
    if args.command == "export":
        # Version 1 emits the canonical JSON manifest and its allowlisted files.
        # The format flag remains explicit so unsupported formats never silently succeed.
        output = create_sanitized_export(workspace, args.snapshot)
        return 0, {"status": "exported", "snapshot_id": args.snapshot, "path": str(output)}
    if args.command == "report-inputs":
        output = create_deliverable_inputs(workspace, args.snapshot)
        return 0, {"status": "generated", "snapshot_id": args.snapshot, "path": str(output)}
    if args.command == "artifacts":
        output = create_final_artifacts(workspace, args.snapshot)
        return 0, {"status": "rendered", "snapshot_id": args.snapshot, "path": str(output)}
    if args.command == "verify":
        verification = verify_snapshot(workspace, args.snapshot)
        return 0, {
            "status": "verified",
            "snapshot_id": args.snapshot,
            "verified_files": verification.verified_files,
        }
    raise InvalidInputError(f"unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None, *, workspace: Path | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        code, payload = _dispatch(args, _workspace(args, workspace))
        _emit(payload, as_json=getattr(args, "json_output", False))
        return code
    except IntegrityError as exc:
        print(f"integrity failure: {exc}", file=sys.stderr)
        return EXIT_INTEGRITY_FAILURE
    except (InvalidInputError, ValidationError, ValueError, FileExistsError) as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except AssessmentError as exc:
        print(f"prerequisite or assessment failure: {exc}", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    except OSError as exc:
        print(f"execution failure: {exc}", file=sys.stderr)
        return EXIT_EXECUTION_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
