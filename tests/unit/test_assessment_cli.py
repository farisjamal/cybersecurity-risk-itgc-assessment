from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from cyber_assess import cli
from cyber_assess.errors import IntegrityError, InvalidInputError, MissingPrerequisiteError


def test_parser_exposes_the_bounded_command_surface() -> None:
    parser = cli.build_parser()

    assert parser.parse_args(["doctor", "--json"]).command == "doctor"
    assert parser.parse_args(["lab", "seed", "--seed", "7"]).seed == 7
    scenario = parser.parse_args(["scenario", "retest", "--id", "S01", "--baseline-run", "RUN-1"])
    assert scenario.scenario_action == "retest"
    assert parser.parse_args(["export", "--snapshot", "SNAP-1"]).format == "all"
    assert parser.parse_args(["report-inputs", "--snapshot", "SNAP-1"]).snapshot == "SNAP-1"
    assert parser.parse_args(["artifacts", "--snapshot", "SNAP-1"]).snapshot == "SNAP-1"


def test_workspace_precedence(tmp_path: Path) -> None:
    explicit = tmp_path / "explicit"
    fallback = tmp_path / "fallback"
    assert cli._workspace(Namespace(workspace=explicit), fallback) == explicit.resolve()
    assert cli._workspace(Namespace(), fallback) == fallback.resolve()


@pytest.mark.parametrize(
    ("args", "patch_name", "patch_result", "expected_code", "expected_key"),
    [
        (
            Namespace(command="doctor"),
            "run_doctor",
            SimpleNamespace(ok=True, as_dict=lambda: {"ok": True}),
            0,
            "ok",
        ),
        (
            Namespace(command="doctor"),
            "run_doctor",
            SimpleNamespace(ok=False, as_dict=lambda: {"ok": False}),
            cli.EXIT_MISSING_PREREQUISITE,
            "ok",
        ),
        (
            Namespace(command="init", engagement="ENG-X"),
            "initialize_engagement",
            Path("assessment/engagement.yaml"),
            0,
            "engagement",
        ),
        (
            Namespace(command="lab", lab_action="up"),
            "run_compose",
            {"status": "completed"},
            0,
            "status",
        ),
        (
            Namespace(command="lab", lab_action="seed", seed=42),
            "seed_lab",
            {"status": "completed", "seed": 42},
            0,
            "seed",
        ),
        (
            Namespace(
                command="scenario",
                scenario_action="run",
                scenario_id="S01",
                baseline_run=None,
            ),
            "route_scenario",
            {"run_id": "RUN-1"},
            0,
            "run_id",
        ),
        (
            Namespace(command="assess", engagement="ENG-X"),
            "validate_assessment",
            SimpleNamespace(
                valid=False,
                errors=("bad",),
                warnings=(),
                validated_ids=(),
            ),
            cli.EXIT_INVALID_INPUT,
            "errors",
        ),
        (
            Namespace(command="findings", engagement="ENG-X"),
            "validate_findings",
            SimpleNamespace(valid=True, errors=(), validated_ids=("FIND-1",)),
            0,
            "validated_ids",
        ),
        (
            Namespace(command="snapshot", engagement="ENG-X"),
            "create_snapshot",
            SimpleNamespace(id="SNAP-1"),
            0,
            "snapshot_id",
        ),
        (
            Namespace(command="export", snapshot="SNAP-1", format="all"),
            "create_sanitized_export",
            Path("outputs/SNAP-1"),
            0,
            "path",
        ),
        (
            Namespace(command="report-inputs", snapshot="SNAP-1"),
            "create_deliverable_inputs",
            Path("outputs/reporting/SNAP-1"),
            0,
            "path",
        ),
        (
            Namespace(command="artifacts", snapshot="SNAP-1"),
            "create_final_artifacts",
            Path("outputs/artifacts/SNAP-1"),
            0,
            "path",
        ),
        (
            Namespace(command="verify", snapshot="SNAP-1"),
            "verify_snapshot",
            SimpleNamespace(verified_files=7),
            0,
            "verified_files",
        ),
    ],
)
def test_dispatch_maps_commands_to_stable_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    args: Namespace,
    patch_name: str,
    patch_result: object,
    expected_code: int,
    expected_key: str,
) -> None:
    monkeypatch.setattr(cli, patch_name, lambda *_args, **_kwargs: patch_result)

    code, payload = cli._dispatch(args, tmp_path)

    assert code == expected_code
    assert expected_key in payload


def test_dispatch_rejects_an_unknown_command(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="unsupported command"):
        cli._dispatch(Namespace(command="unknown"), tmp_path)


def test_main_emits_json_and_maps_domain_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "run_doctor",
        lambda _workspace: SimpleNamespace(ok=True, as_dict=lambda: {"ok": True}),
    )
    assert cli.main(["doctor", "--json"], workspace=tmp_path) == 0
    assert '"ok": true' in capsys.readouterr().out

    failures = [
        (IntegrityError("tampered"), cli.EXIT_INTEGRITY_FAILURE, "integrity failure"),
        (InvalidInputError("bad"), cli.EXIT_INVALID_INPUT, "invalid input"),
        (
            MissingPrerequisiteError("missing"),
            cli.EXIT_MISSING_PREREQUISITE,
            "prerequisite or assessment failure",
        ),
        (OSError("disk"), cli.EXIT_EXECUTION_FAILURE, "execution failure"),
    ]
    for error, expected_code, expected_message in failures:
        monkeypatch.setattr(
            cli, "_dispatch", lambda *_args, _error=error: (_ for _ in ()).throw(_error)
        )
        assert cli.main(["doctor"], workspace=tmp_path) == expected_code
        assert expected_message in capsys.readouterr().err


def test_emit_human_output_skips_transport_keys(capsys: pytest.CaptureFixture[str]) -> None:
    cli._emit({"status": "created", "snapshot_id": "SNAP-1"}, as_json=False)
    output = capsys.readouterr().out
    assert output == "created\nsnapshot_id: SNAP-1\n"
