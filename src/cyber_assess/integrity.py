"""Path containment and content integrity primitives."""

from __future__ import annotations

import hashlib
from pathlib import Path

from cyber_assess.errors import IntegrityError, InvalidInputError


class PathOutsideWorkspaceError(InvalidInputError):
    """A record attempted to escape the approved workspace."""


def resolve_within(root: Path, candidate: str | Path, *, must_exist: bool = False) -> Path:
    """Resolve *candidate* and reject paths outside *root*, including traversal."""
    canonical_root = root.resolve()
    raw_candidate = Path(candidate)
    resolved = (
        raw_candidate if raw_candidate.is_absolute() else canonical_root / raw_candidate
    ).resolve()
    try:
        resolved.relative_to(canonical_root)
    except ValueError as exc:
        raise PathOutsideWorkspaceError(f"path is outside workspace: {candidate}") from exc
    if must_exist and not resolved.exists():
        raise InvalidInputError(f"required path does not exist: {candidate}")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(root: Path, relative_path: str, expected_hash: str, expected_size: int) -> Path:
    path = resolve_within(root, relative_path, must_exist=True)
    if path.is_symlink():
        raise IntegrityError(f"symbolic links are not accepted as evidence: {relative_path}")
    if sha256_file(path) != expected_hash:
        raise IntegrityError(f"hash mismatch for {relative_path}")
    if path.stat().st_size != expected_size:
        raise IntegrityError(f"size mismatch for {relative_path}")
    return path
