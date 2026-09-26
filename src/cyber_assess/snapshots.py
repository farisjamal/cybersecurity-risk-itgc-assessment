"""Frozen source snapshots, verification, and sanitized distribution manifests."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cyber_assess import __version__
from cyber_assess.errors import IntegrityError, InvalidInputError
from cyber_assess.integrity import resolve_within, sha256_file, verify_file
from cyber_assess.models import Evidence, ExportSnapshot, Finding, Retest, SnapshotSource
from cyber_assess.validation import validate_assessment
from cyber_assess.yamlio import dump_yaml, load_model, load_models


class IntegrityVerificationError(IntegrityError):
    """A snapshot source no longer matches its frozen digest."""


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    verified_files: int


def _source_paths(workspace: Path) -> list[Path]:
    assessment = workspace / "assessment"
    sources = [
        path
        for path in assessment.rglob("*.yaml")
        if "snapshots" not in path.relative_to(assessment).parts
    ]
    for evidence in load_models(assessment / "evidence", Evidence):
        sources.append(resolve_within(workspace, evidence.path, must_exist=True))
    unique = {path.resolve(): path.resolve() for path in sources}
    return sorted(
        unique.values(), key=lambda item: item.relative_to(workspace.resolve()).as_posix()
    )


def create_snapshot(
    workspace: Path, engagement_id: str, *, created_at: str | datetime | None = None
) -> ExportSnapshot:
    workspace = workspace.resolve()
    validation = validate_assessment(workspace, engagement_id)
    if not validation.valid:
        raise InvalidInputError("assessment validation failed: " + "; ".join(validation.errors))
    sources = [
        SnapshotSource(
            schema_version="1.0",
            path=path.relative_to(workspace).as_posix(),
            sha256=sha256_file(path),
            size=path.stat().st_size,
        )
        for path in _source_paths(workspace)
    ]
    if isinstance(created_at, str):
        instant = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    else:
        instant = created_at or datetime.now(UTC)
    seed = "".join(f"{source.path}:{source.sha256}" for source in sources)
    import hashlib

    short_hash = hashlib.sha256(seed.encode()).hexdigest()[:8].upper()
    snapshot_id = f"SNAP-{instant:%Y%m%dT%H%M%S}-{short_hash}"
    findings = load_models(workspace / "assessment" / "findings", Finding)
    retests = load_models(workspace / "assessment" / "retests", Retest)
    snapshot = ExportSnapshot(
        schema_version="1.0",
        id=snapshot_id,
        engagement_id=engagement_id,
        generator_version=__version__,
        created_at=instant,
        source_hashes=sources,
        baseline_ids=[finding.id for finding in findings],
        retest_ids=[retest.id for retest in retests],
    )
    destination = workspace / "assessment" / "snapshots" / f"{snapshot.id}.yaml"
    if destination.exists():
        raise FileExistsError(f"snapshot already exists: {snapshot.id}")
    dump_yaml(destination, snapshot)
    return snapshot


def load_snapshot(workspace: Path, snapshot_id: str) -> ExportSnapshot:
    path = workspace / "assessment" / "snapshots" / f"{snapshot_id}.yaml"
    return load_model(path, ExportSnapshot)


def verify_snapshot(workspace: Path, snapshot_id: str) -> VerificationResult:
    snapshot = load_snapshot(workspace, snapshot_id)
    try:
        for source in snapshot.source_hashes:
            verify_file(workspace, source.path, source.sha256, source.size)
    except IntegrityError as exc:
        raise IntegrityVerificationError(str(exc)) from exc
    return VerificationResult(True, len(snapshot.source_hashes))


def _sanitized_sources(workspace: Path, snapshot: ExportSnapshot) -> list[SnapshotSource]:
    evidence_records = load_models(workspace / "assessment" / "evidence", Evidence)
    excluded_paths = {
        evidence.path for evidence in evidence_records if evidence.sensitivity != "sanitized"
    }
    allowed_extensions = {".yaml", ".yml", ".json", ".csv", ".md", ".txt", ".html"}
    sanitized: list[SnapshotSource] = []
    for source in snapshot.source_hashes:
        if source.path in excluded_paths or source.path.startswith("runtime/"):
            continue
        path = resolve_within(workspace, source.path, must_exist=True)
        if path.is_symlink() or path.suffix.lower() not in allowed_extensions:
            continue
        sanitized.append(source)
    return sanitized


def create_sanitized_export(
    workspace: Path, snapshot_id: str, *, output_root: Path | None = None
) -> Path:
    """Copy allowlisted snapshot sources through a temporary directory, then publish atomically."""
    verify_snapshot(workspace, snapshot_id)
    snapshot = load_snapshot(workspace, snapshot_id)
    export_root = (output_root or workspace / "outputs").resolve()
    export_root.mkdir(parents=True, exist_ok=True)
    destination = export_root / snapshot_id
    if destination.exists():
        raise FileExistsError(f"export already exists: {destination}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{snapshot_id}.", dir=export_root))
    try:
        artifacts: list[dict[str, object]] = []
        for source in _sanitized_sources(workspace, snapshot):
            source_path = resolve_within(workspace, source.path, must_exist=True)
            target = temporary / "artifacts" / source.path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target)
            artifacts.append(
                {
                    "path": f"artifacts/{source.path}",
                    "sha256": source.sha256,
                    "size": source.size,
                    "classification": "sanitized",
                }
            )
        manifest = {
            "schema_version": "1.0",
            "snapshot_id": snapshot.id,
            "engagement_id": snapshot.engagement_id,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "artifacts": artifacts,
            "limitations": [
                "Synthetic and local lab material only.",
                "The manifest detects modification but does not prove independent authenticity.",
            ],
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination
