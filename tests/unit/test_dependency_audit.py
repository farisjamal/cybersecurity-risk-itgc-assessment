import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from cyber_assess.dependency_audit import audit_dependencies


@pytest.mark.parametrize("response", ["", "not JSON", '{"dependencies":[]}'])
def test_missing_feed_results_never_become_a_clean_scan(tmp_path: Path, response: str) -> None:
    (tmp_path / "requirements.lock").write_text("example==1.0", encoding="utf-8")
    with patch(
        "cyber_assess.dependency_audit.subprocess.run",
        return_value=SimpleNamespace(returncode=1, stdout=response),
    ):
        result = audit_dependencies(tmp_path)
    assert result["status"] == "unavailable"
    assert result["vulnerability_count"] is None
    assert result["limitations"]


def test_scanner_timeout_is_persisted_as_incomplete(tmp_path: Path) -> None:
    (tmp_path / "requirements.lock").write_text("example==1.0", encoding="utf-8")
    with patch(
        "cyber_assess.dependency_audit.subprocess.run",
        side_effect=subprocess.TimeoutExpired("scanner", 120),
    ):
        result = audit_dependencies(tmp_path)
    assert result["status"] == "unavailable"
    stored = json.loads((tmp_path / "runtime/dependency-audit.json").read_text(encoding="utf-8"))
    assert stored["vulnerability_count"] is None


@pytest.mark.parametrize(
    "vulns,status,code", [([], "clean", 0), ([{"id": "TEST-01"}], "vulnerabilities_found", 1)]
)
def test_completed_scan_retains_actual_advisory_count(
    tmp_path: Path, vulns: list[dict[str, str]], status: str, code: int
) -> None:
    (tmp_path / "requirements.lock").write_text("example==1.0", encoding="utf-8")
    payload = {"dependencies": [{"name": "example", "version": "1.0", "vulns": vulns}]}
    with patch(
        "cyber_assess.dependency_audit.subprocess.run",
        return_value=SimpleNamespace(returncode=code, stdout=json.dumps(payload)),
    ):
        result = audit_dependencies(tmp_path)
    assert result["status"] == status
    assert result["vulnerability_count"] == len(vulns)


def test_skipped_package_is_not_a_clean_assessment(tmp_path: Path) -> None:
    (tmp_path / "requirements.lock").write_text("example==1.0", encoding="utf-8")
    payload = {"dependencies": [{"name": "example", "skip_reason": "not available", "vulns": []}]}
    with patch(
        "cyber_assess.dependency_audit.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload)),
    ):
        result = audit_dependencies(tmp_path)
    assert result["status"] == "unavailable"
