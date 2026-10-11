from __future__ import annotations

import json
import shutil
import stat
import time
from pathlib import Path

import pytest

from cyber_assess.artifacts import create_final_artifacts
from cyber_assess.integrity import sha256_file
from cyber_assess.models import Evidence
from cyber_assess.snapshots import create_snapshot
from cyber_assess.yamlio import dump_yaml, load_models


@pytest.mark.acceptance
def test_two_hundred_evidence_records_export_without_truncation(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / "assessment", tmp_path / "assessment")
    shutil.copytree(root / "fixtures", tmp_path / "fixtures")
    # Docker build contexts can preserve read-only Windows fixture directory modes.
    for directory in (item for item in tmp_path.rglob("*") if item.is_dir()):
        directory.chmod(directory.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)
    existing = load_models(tmp_path / "assessment/evidence", Evidence)
    for number in range(200 - len(existing)):
        path = tmp_path / "fixtures/evidence/capacity" / f"record-{number:03d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"synthetic_capacity_record": number}), encoding="utf-8")
        record = existing[0].model_copy(
            update={
                "id": f"EVID-CAPACITY-{number:03d}",
                "path": path.relative_to(tmp_path).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
                "media_type": "application/json",
                "provenance": "synthetic_record",
                "run_id": "RUN-CAPACITY",
                "query_or_action": "Generate capacity-only fixture",
            }
        )
        dump_yaml(tmp_path / "assessment/evidence" / f"{record.id}.yaml", record)
    started = time.perf_counter()
    snapshot = create_snapshot(tmp_path, "ENG-001")
    bundle = create_final_artifacts(tmp_path, snapshot.id)
    elapsed = time.perf_counter() - started
    reconciliation = json.loads((bundle / "reconciliation.json").read_text(encoding="utf-8"))
    assert reconciliation["record_counts"]["evidence"] == 200
    assert reconciliation["record_counts"]["controls"] == 20
    assert reconciliation["snapshot_alignment"]["unmatched_references"] == 0
    assert elapsed < 60, f"Validated export exceeded the PRD target: {elapsed:.2f}s"
