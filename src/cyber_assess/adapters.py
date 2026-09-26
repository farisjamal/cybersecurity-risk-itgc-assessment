"""Bounded Compose adapters; PostgreSQL remains private to the Compose network."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from cyber_assess.errors import InvalidInputError, MissingPrerequisiteError

SCENARIO_IDS = frozenset({"S01", "S02", "S03", "S04", "S05", "S06"})
RESOURCE_PATTERN = re.compile(r"^cyber-assess-scenario-[a-z0-9-]{8,64}$")


def _docker() -> str:
    executable = shutil.which("docker")
    if executable is None:
        raise MissingPrerequisiteError("Docker CLI is unavailable")
    return executable


def _run(workspace: Path, command: list[str], *, timeout: int = 120) -> str:
    try:
        # Callers construct argv from fixed tokens and explicitly allowlisted IDs.
        result = subprocess.run(  # noqa: S603
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise MissingPrerequisiteError(f"container command is unavailable: {exc}") from exc
    if result.returncode:
        message = (result.stderr or result.stdout).strip()
        raise MissingPrerequisiteError(f"container command failed: {message}")
    return result.stdout.strip()


def run_compose(workspace: Path, action: str) -> dict[str, object]:
    if action not in {"up", "stop"}:
        raise InvalidInputError(f"unsupported lab action: {action}")
    command = [
        _docker(),
        "compose",
        "-p",
        "example-bank-lab",
        "-f",
        "compose.yaml",
    ]
    command += ["up", "-d"] if action == "up" else ["stop"]
    _run(workspace, command)
    return {"status": "completed", "action": action, "project": "example-bank-lab"}


def _app_command(workspace: Path, arguments: list[str]) -> dict[str, Any]:
    command = [
        _docker(),
        "compose",
        "-p",
        "example-bank-lab",
        "-f",
        "compose.yaml",
        "exec",
        "-T",
        "app",
        "python",
        "-m",
        "bank_lab",
        *arguments,
    ]
    output = _run(workspace, command)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise MissingPrerequisiteError("bank_lab returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise MissingPrerequisiteError("bank_lab returned a non-object result")
    return cast(dict[str, Any], payload)


def seed_lab(workspace: Path, seed: int) -> dict[str, object]:
    if seed < 0:
        raise InvalidInputError("seed must be zero or greater")
    result = _app_command(workspace, ["seed", "--seed", str(seed)])
    return {"status": "completed", "seed": seed, "summary": result}


def _load_run(workspace: Path, run_id: str) -> dict[str, Any]:
    run_path = workspace / "assessment" / "scenario_runs" / f"{run_id}.json"
    if not run_path.exists():
        raise InvalidInputError(f"scenario run not found: {run_id}")
    payload = json.loads(run_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InvalidInputError(f"invalid scenario run record: {run_id}")
    return payload


def _write_run(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = workspace / "assessment" / "scenario_runs" / f"{payload['run_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"scenario run already exists: {payload['run_id']}")
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def _latest_remediation(workspace: Path, scenario_id: str, baseline_run_id: str) -> dict[str, Any]:
    run_directory = workspace / "assessment" / "scenario_runs"
    runs = sorted(
        (json.loads(path.read_text(encoding="utf-8")) for path in run_directory.glob("*.json")),
        key=lambda item: item.get("recorded_at", ""),
    )
    remediation = next(
        (
            item
            for item in reversed(runs)
            if item.get("action") == "remediate"
            and item.get("scenario_id") == scenario_id
            and item.get("baseline_run_id") == baseline_run_id
        ),
        None,
    )
    if remediation is None:
        raise InvalidInputError("retest requires a completed remediation run")
    return cast(dict[str, Any], remediation)


def route_scenario(
    workspace: Path, action: str, scenario_id: str, *, baseline_run_id: str | None = None
) -> dict[str, Any]:
    if scenario_id not in SCENARIO_IDS:
        raise InvalidInputError(f"unsupported scenario ID: {scenario_id}")
    if action not in {"run", "remediate", "retest"}:
        raise InvalidInputError(f"unsupported scenario action: {action}")

    baseline: dict[str, Any] | None = None
    if action != "run":
        if baseline_run_id is None:
            raise InvalidInputError(f"scenario {action} requires --baseline-run")
        baseline = _load_run(workspace, baseline_run_id)
        if baseline.get("scenario_id") != scenario_id or baseline.get("action") != "run":
            raise InvalidInputError("baseline run does not own the requested scenario")

    if action == "run":
        resource_name = f"cyber-assess-scenario-{scenario_id.lower()}-{uuid4().hex[:12]}"
        arguments = ["scenario", "run", "--id", scenario_id, "--resource", resource_name]
    elif action == "remediate":
        assert baseline is not None
        resource_name = str(baseline["resource_name"])
        arguments = [
            "scenario",
            "remediate",
            "--id",
            scenario_id,
            "--resource",
            resource_name,
            "--baseline-run",
            str(baseline_run_id),
        ]
    else:
        assert baseline_run_id is not None
        remediation = _latest_remediation(workspace, scenario_id, baseline_run_id)
        resource_name = str(baseline["resource_name"]) if baseline is not None else ""
        arguments = [
            "scenario",
            "retest",
            "--id",
            scenario_id,
            "--baseline-run",
            baseline_run_id,
            "--remediation-run",
            str(remediation["run_id"]),
        ]
    if not RESOURCE_PATTERN.fullmatch(resource_name):
        raise InvalidInputError("scenario resource failed the fixed project allowlist")

    result = _app_command(workspace, arguments)
    run_id = str(result.get("run_id") or f"RUN-{scenario_id}-{uuid4().hex[:12].upper()}")
    payload = {
        "schema_version": "1.0",
        "run_id": run_id,
        "scenario_id": scenario_id,
        "action": action,
        "baseline_run_id": baseline_run_id,
        "resource_name": resource_name,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "result": result,
    }
    return _write_run(workspace, payload)
