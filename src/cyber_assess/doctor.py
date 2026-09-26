"""Non-secret environment diagnostics."""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class DoctorResult:
    ok: bool
    python: str
    workspace_writable: bool
    docker_cli: bool
    docker_engine: bool
    port_8000_available: bool
    problems: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _port_available(port: int) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def run_doctor(workspace: Path) -> DoctorResult:
    problems: list[str] = []
    writable = workspace.exists() and workspace.is_dir() and shutil.disk_usage(workspace).free > 0
    if not writable:
        problems.append("workspace is unavailable or not writable")
    docker_executable = shutil.which("docker")
    docker_cli = docker_executable is not None
    docker_engine = False
    if not docker_cli:
        problems.append("Docker CLI is unavailable")
    else:
        try:
            docker_command = str(docker_executable)
            check = subprocess.run(  # noqa: S603 - executable resolved by shutil.which
                [docker_command, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            docker_engine = check.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            docker_engine = False
        if not docker_engine:
            problems.append("Docker engine is unavailable")
    port_available = _port_available(8000)
    if not port_available:
        problems.append("loopback port 8000 is already in use")
    return DoctorResult(
        ok=not problems,
        python=sys.version.split()[0],
        workspace_writable=writable,
        docker_cli=docker_cli,
        docker_engine=docker_engine,
        port_8000_available=port_available,
        problems=tuple(problems),
    )
