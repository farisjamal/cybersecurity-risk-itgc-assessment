from __future__ import annotations

import json
from pathlib import Path

import pytest

from cyber_assess.bootstrap import initialize_engagement
from cyber_assess.snapshots import (
    IntegrityVerificationError,
    create_sanitized_export,
    create_snapshot,
    verify_snapshot,
)
from cyber_assess.validation import validate_assessment


def test_initialize_does_not_overwrite_existing_engagement(tmp_path: Path) -> None:
    initialize_engagement(tmp_path, "ENG-TEST")
    engagement = tmp_path / "assessment" / "engagement.yaml"
    original = engagement.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError):
        initialize_engagement(tmp_path, "ENG-SECOND")

    assert engagement.read_text(encoding="utf-8") == original


def test_snapshot_detects_tampered_source(tmp_path: Path) -> None:
    initialize_engagement(tmp_path, "ENG-TEST")
    snapshot = create_snapshot(tmp_path, "ENG-TEST", created_at="2026-09-25T15:00:00Z")
    assert verify_snapshot(tmp_path, snapshot.id).valid

    (tmp_path / "assessment" / "engagement.yaml").write_text(
        "schema_version: '1.0'\nid: TAMPERED\n", encoding="utf-8"
    )
    with pytest.raises(IntegrityVerificationError, match="hash mismatch"):
        verify_snapshot(tmp_path, snapshot.id)


def test_sanitized_export_manifest_excludes_restricted_evidence(tmp_path: Path) -> None:
    initialize_engagement(tmp_path, "ENG-TEST")
    snapshot = create_snapshot(tmp_path, "ENG-TEST", created_at="2026-09-25T15:00:00Z")
    export_dir = create_sanitized_export(tmp_path, snapshot.id, output_root=tmp_path / "exports")
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["snapshot_id"] == snapshot.id
    assert all(item["classification"] == "sanitized" for item in manifest["artifacts"])
    assert all("runtime" not in item["path"] for item in manifest["artifacts"])


def test_minimal_initialized_engagement_validates(tmp_path: Path) -> None:
    initialize_engagement(tmp_path, "ENG-TEST")
    result = validate_assessment(tmp_path, "ENG-TEST")
    assert result.valid
    assert result.errors == ()
