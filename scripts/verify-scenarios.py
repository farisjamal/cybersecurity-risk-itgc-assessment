"""Execute six scenario chains in separate Compose projects and verify baseline isolation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from cyber_assess.adapters import route_scenario, seed_lab


def main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    before = seed_lab(workspace, 42)["summary"]
    results = []
    for number in range(1, 7):
        scenario_id = f"S{number:02d}"
        baseline = route_scenario(workspace, "run", scenario_id)
        baseline_id = str(baseline["run_id"])
        remediation = route_scenario(
            workspace, "remediate", scenario_id, baseline_run_id=baseline_id
        )
        retest = route_scenario(workspace, "retest", scenario_id, baseline_run_id=baseline_id)
        passed = retest["result"]["observations"]["passed"] is True
        results.append(
            {
                "scenario_id": scenario_id,
                "baseline": baseline,
                "remediation": remediation,
                "retest": retest,
            }
        )
        print(json.dumps({"scenario_id": scenario_id, "passed": passed}), flush=True)
        if not passed:
            raise RuntimeError(f"{scenario_id} failed its fresh retest")
    after = seed_lab(workspace, 42)["summary"]
    if before != after:
        raise RuntimeError("Default lab population changed during scenario execution")
    output = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "source_population_unchanged": True,
        "default_lab_summary": after,
        "scenario_count": len(results),
        "scenario_runs": results,
        "limitations": [
            "Scenario baselines are deliberately injected synthetic exceptions.",
            "Containers and networks are stopped after retest; scoped volumes remain for review.",
            "Reproduction tests do not establish enterprise control effectiveness.",
        ],
    }
    path = workspace / "runtime/scenario-verification.json"
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
