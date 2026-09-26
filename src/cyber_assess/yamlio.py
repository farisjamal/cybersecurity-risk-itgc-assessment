"""Safe YAML loading and atomic serialization for canonical records."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from cyber_assess.errors import InvalidInputError
from cyber_assess.integrity import resolve_within


def load_yaml(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise InvalidInputError(f"cannot load YAML {path}: {exc}") from exc


def load_model[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate(load_yaml(path))
    except Exception as exc:
        if isinstance(exc, InvalidInputError):
            raise
        raise InvalidInputError(f"invalid {model.__name__} record {path}: {exc}") from exc


def load_models[ModelT: BaseModel](directory: Path, model: type[ModelT]) -> list[ModelT]:
    if not directory.exists():
        return []
    records = [load_model(path, model) for path in sorted(directory.glob("*.yaml"))]
    ids = [getattr(record, "id", None) for record in records]
    if len(ids) != len(set(ids)):
        raise InvalidInputError(f"duplicate IDs in {directory}")
    return records


def dump_yaml(path: Path, value: BaseModel | dict[str, Any] | list[Any]) -> None:
    """Atomically write a YAML value without serializing Python-specific tags."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] | list[Any]
    if isinstance(value, BaseModel):
        data = value.model_dump(mode="json", exclude_none=True)
    else:
        data = value
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            yaml.safe_dump(data, stream, sort_keys=False, allow_unicode=True)
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def assessment_path(workspace: Path, relative_path: str, *, must_exist: bool = False) -> Path:
    return resolve_within(workspace, Path("assessment") / relative_path, must_exist=must_exist)
