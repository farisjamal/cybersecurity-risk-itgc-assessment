from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from cyber_assess import adapters
from cyber_assess.errors import InvalidInputError, MissingPrerequisiteError


def test_docker_requires_an_installed_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapters.shutil, "which", lambda _name: None)

    with pytest.raises(MissingPrerequisiteError, match="Docker CLI"):
        adapters._docker()


def test_run_maps_process_failures_to_stable_prerequisite_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        adapters.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="engine unavailable"
        ),
    )
    with pytest.raises(MissingPrerequisiteError, match="engine unavailable"):
        adapters._run(tmp_path, ["docker", "info"])

    def time_out(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("docker", 1)

    monkeypatch.setattr(adapters.subprocess, "run", time_out)
    with pytest.raises(MissingPrerequisiteError, match="unavailable"):
        adapters._run(tmp_path, ["docker", "info"])


@pytest.mark.parametrize(
    ("action", "tail"),
    [("up", ["up", "-d"]), ("stop", ["stop"])],
)
def test_compose_actions_use_the_fixed_project_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    tail: list[str],
) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(adapters, "_docker", lambda: "docker")
    monkeypatch.setattr(
        adapters,
        "_run",
        lambda _workspace, command, **_kwargs: commands.append(command) or "",
    )

    result = adapters.run_compose(tmp_path, action)

    assert result == {
        "status": "completed",
        "action": action,
        "project": "cybersecurity-itgc-lab",
    }
    assert commands[0][:6] == [
        "docker",
        "compose",
        "-p",
        "cybersecurity-itgc-lab",
        "-f",
        "compose.yaml",
    ]
    assert commands[0][-len(tail) :] == tail


def test_compose_and_seed_reject_unbounded_inputs(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="unsupported lab action"):
        adapters.run_compose(tmp_path, "destroy")
    with pytest.raises(InvalidInputError, match="zero or greater"):
        adapters.seed_lab(tmp_path, -1)


def test_app_command_requires_a_json_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(adapters, "_docker", lambda: "docker")
    monkeypatch.setattr(adapters, "_run", lambda *_args, **_kwargs: "not-json")
    with pytest.raises(MissingPrerequisiteError, match="invalid JSON"):
        adapters._app_command(tmp_path, ["seed"])


def test_scenarios_use_a_separate_compose_project_and_no_default_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(adapters, "_docker", lambda: "docker")
    monkeypatch.setattr(
        adapters,
        "_run",
        lambda _workspace, command, **_kwargs: commands.append(command) or '{"run_id":"RUN-TEST"}',
    )
    resource = "cyber-assess-scenario-s01-0123456789ab"
    adapters._scenario_command(tmp_path, ["scenario", "run"], resource, "S01")
    assert commands[0][3] == resource
    assert "infra/docker/compose.scenario.yaml" in commands[0]
    assert "run" in commands[0] and "--no-deps" in commands[0]
    assert "exec" not in commands[0]
    assert "BANK_LAB_SCENARIO_ID=S01" in commands[0]
    adapters._stop_scenario(tmp_path, resource)
    assert commands[1][3] == resource
    assert commands[1][-3:] == ["down", "--timeout", "10"]
    assert "--volumes" not in commands[1]
    with pytest.raises(InvalidInputError, match="project allowlist"):
        adapters._scenario_compose(adapters.LAB_PROJECT)

    monkeypatch.setattr(adapters, "_run", lambda *_args, **_kwargs: "[]")
    with pytest.raises(MissingPrerequisiteError, match="non-object"):
        adapters._app_command(tmp_path, ["seed"])


def test_seed_passes_only_the_numeric_seed_to_the_lab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        adapters,
        "_app_command",
        lambda _workspace, arguments: {"arguments": arguments},
    )

    result = adapters.seed_lab(tmp_path, 42)

    assert result["seed"] == 42
    assert result["summary"] == {"arguments": ["seed", "--seed", "42"]}


def test_scenario_chain_requires_owned_baseline_and_remediation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    responses = iter(
        [
            {"run_id": "RUN-S01-BASELINE", "passed": False},
            {"run_id": "RUN-S01-REMEDIATE", "passed": True},
            {"run_id": "RUN-S01-RETEST", "passed": True},
        ]
    )
    calls: list[list[str]] = []

    def app_command(
        _workspace: Path, arguments: list[str], _resource: str, _scenario: str
    ) -> dict[str, object]:
        calls.append(arguments)
        return next(responses)

    monkeypatch.setattr(adapters, "_scenario_command", app_command)
    monkeypatch.setattr(adapters, "_prepare_scenario", lambda *_args: None)
    monkeypatch.setattr(adapters, "_stop_scenario", lambda *_args: None)
    baseline = adapters.route_scenario(tmp_path, "run", "S01")
    remediation = adapters.route_scenario(
        tmp_path, "remediate", "S01", baseline_run_id=str(baseline["run_id"])
    )
    retest = adapters.route_scenario(
        tmp_path, "retest", "S01", baseline_run_id=str(baseline["run_id"])
    )

    assert baseline["resource_name"].startswith("cyber-assess-scenario-s01-")
    assert remediation["baseline_run_id"] == baseline["run_id"]
    assert retest["result"] == {"run_id": "RUN-S01-RETEST", "passed": True}
    assert "RUN-S01-REMEDIATE" in calls[2]


def test_scenario_router_rejects_invalid_or_inconsistent_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(InvalidInputError, match="unsupported scenario ID"):
        adapters.route_scenario(tmp_path, "run", "S99")
    with pytest.raises(InvalidInputError, match="unsupported scenario action"):
        adapters.route_scenario(tmp_path, "delete", "S01")
    with pytest.raises(InvalidInputError, match="requires --baseline-run"):
        adapters.route_scenario(tmp_path, "retest", "S01")
    with pytest.raises(InvalidInputError, match="not found"):
        adapters.route_scenario(tmp_path, "remediate", "S01", baseline_run_id="MISSING")

    run_dir = tmp_path / "assessment" / "scenario_runs"
    run_dir.mkdir(parents=True)
    (run_dir / "WRONG.json").write_text(
        json.dumps({"run_id": "WRONG", "scenario_id": "S02", "action": "run"}),
        encoding="utf-8",
    )
    with pytest.raises(InvalidInputError, match="does not own"):
        adapters.route_scenario(tmp_path, "remediate", "S01", baseline_run_id="WRONG")

    baseline = {
        "run_id": "BASELINE",
        "scenario_id": "S01",
        "action": "run",
        "resource_name": "cyber-assess-scenario-s01-valid123",
    }
    (run_dir / "BASELINE.json").write_text(json.dumps(baseline), encoding="utf-8")
    with pytest.raises(InvalidInputError, match="completed remediation"):
        adapters.route_scenario(tmp_path, "retest", "S01", baseline_run_id="BASELINE")

    monkeypatch.setattr(adapters, "_scenario_command", lambda *_args: {"run_id": "DUPLICATE"})
    monkeypatch.setattr(adapters, "_prepare_scenario", lambda *_args: None)
    (run_dir / "DUPLICATE.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        adapters.route_scenario(tmp_path, "run", "S01")
