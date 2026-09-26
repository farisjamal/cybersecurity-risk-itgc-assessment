from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from cyber_assess import doctor


def test_port_probe_reports_bind_conflicts(monkeypatch: pytest.MonkeyPatch) -> None:
    class BusySocket:
        def __enter__(self) -> BusySocket:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def bind(self, _address: tuple[str, int]) -> None:
            raise OSError("busy")

    monkeypatch.setattr(doctor.socket, "socket", BusySocket)
    assert doctor._port_available(8000) is False


def test_doctor_reports_a_ready_local_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda _name: "docker")
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(doctor, "_port_available", lambda _port: True)

    result = doctor.run_doctor(tmp_path)

    assert result.ok
    assert result.docker_cli and result.docker_engine
    assert result.problems == ()
    assert result.as_dict()["workspace_writable"] is True


def test_doctor_accumulates_non_secret_failure_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr(doctor.shutil, "which", lambda _name: None)
    monkeypatch.setattr(doctor, "_port_available", lambda _port: False)

    result = doctor.run_doctor(missing)

    assert not result.ok
    assert result.problems == (
        "workspace is unavailable or not writable",
        "Docker CLI is unavailable",
        "loopback port 8000 is already in use",
    )


def test_doctor_handles_engine_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda _name: "docker")
    monkeypatch.setattr(doctor, "_port_available", lambda _port: True)

    def time_out(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("docker", 10)

    monkeypatch.setattr(doctor.subprocess, "run", time_out)

    result = doctor.run_doctor(tmp_path)

    assert not result.ok
    assert result.problems == ("Docker engine is unavailable",)
