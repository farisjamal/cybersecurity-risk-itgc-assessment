from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_project_metadata_preserves_owner_and_python_contract() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["requires-python"] == ">=3.12,<3.13"
    assert metadata["project"]["authors"] == [
        {
            "name": "Faris Jamal",
            "email": "111167160+farisjamal@users.noreply.github.com",
        }
    ]
    assert metadata["tool"]["pytest"]["ini_options"]["addopts"][-1] == "--cov-fail-under=80"


def test_prd_keeps_required_control_scenario_and_acceptance_counts() -> None:
    prd = (ROOT / "PRD.md").read_text(encoding="utf-8")

    controls = set(re.findall(r"^\| ((?:GOV|IAM|CHG|OPS|IR|DR)-\d{2}) \|", prd, re.MULTILINE))
    scenarios = set(re.findall(r"^\| (S\d{2}) \|", prd, re.MULTILINE))
    acceptance = set(re.findall(r"^\| (AT-\d{2}) \|", prd, re.MULTILINE))

    assert len(controls) == 20
    assert scenarios == {f"S{number:02d}" for number in range(1, 7)}
    assert acceptance == {f"AT-{number:02d}" for number in range(1, 21)}
