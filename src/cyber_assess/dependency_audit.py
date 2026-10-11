"""Record advisory-feed failures explicitly rather than reporting a clean scan."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cyber_assess.integrity import sha256_file


def audit_dependencies(workspace: Path) -> dict[str, Any]:
    requirement = workspace / "requirements.lock"
    result: dict[str, Any] = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "requirements_sha256": sha256_file(requirement),
        "status": "unavailable",
        "dependency_count": None,
        "vulnerability_count": None,
        "limitations": [
            "Advisory retrieval did not complete; no clean-scan conclusion is supported."
        ],
    }
    try:
        process = subprocess.run(  # noqa: S603 - fixed local module and requirement file
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--requirement",
                str(requirement),
                "--disable-pip",
                "--progress-spinner",
                "off",
                "--format",
                "json",
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        payload = json.loads(process.stdout)
        dependencies = payload.get("dependencies") if isinstance(payload, dict) else None
        # Skipped packages make the assessment incomplete, even on scanner exit zero.
        if (
            isinstance(dependencies, list)
            and bool(dependencies)
            and process.returncode in {0, 1}
            and all(
                isinstance(item, dict)
                and isinstance(item.get("vulns"), list)
                and "skip_reason" not in item
                for item in dependencies
            )
        ):
            count = sum(len(item["vulns"]) for item in dependencies)
            if process.returncode == 0 or count:
                result.update(
                    status="clean" if count == 0 else "vulnerabilities_found",
                    dependency_count=len(dependencies),
                    vulnerability_count=count,
                    dependencies=dependencies,
                    limitations=[
                        "Point-in-time advisory coverage for the locked Python packages only."
                    ],
                )
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        pass
    destination = workspace / "runtime/dependency-audit.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in result.items() if key != "dependencies"}
