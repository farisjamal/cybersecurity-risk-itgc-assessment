"""Fail publication checks without printing credential values or matched source lines."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from cyber_assess.errors import MissingPrerequisiteError

FORBIDDEN_SUFFIXES = frozenset(
    {
        ".pem",
        ".key",
        ".pfx",
        ".p12",
        ".jks",
        ".keystore",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".sql",
        ".dump",
        ".har",
        ".pcap",
        ".pcapng",
        ".zip",
        ".7z",
        ".rar",
        ".tar",
        ".gz",
        ".tgz",
        ".pdf",
        ".xlsx",
        ".docx",
        ".pptx",
    }
)
FORBIDDEN_NAMES = frozenset(
    {
        "credentials.json",
        "initial-credentials.json",
        "secrets.toml",
        ".npmrc",
        ".pypirc",
        "id_rsa",
        "id_ed25519",
    }
)
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    re.compile(rb"\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,})\b"),
    re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
)
JSON_SECRET_FIELDS = frozenset(
    {
        "password",
        "password_hash",
        "totp_secret",
        "totp_secrets",
        "api_key",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
        "database_url",
        "session_pepper",
    }
)


def forbidden_path(value: str) -> bool:
    path = PurePosixPath(value.casefold())
    if value == ".env.example":
        return False
    return (
        path.name == ".env"
        or path.name.startswith(".env.")
        or path.name in FORBIDDEN_NAMES
        or path.suffix in FORBIDDEN_SUFFIXES
        or any(part in {".aws", ".ssh", ".azure", ".kube"} for part in path.parts)
        or (path.parts[0] in {"runtime", "outputs", "portfolio"} and path.name != ".gitkeep")
    )


def _json_has_credentials(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.casefold() in JSON_SECRET_FIELDS or _json_has_credentials(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_json_has_credentials(item) for item in value)
    return False


def inspect_payload(files: dict[str, bytes]) -> list[str]:
    errors: list[str] = []
    if ".gitignore" not in files:
        errors.append(".gitignore: shared exclusion rules must be included")
    for name, content in files.items():
        if forbidden_path(name):
            errors.append(f"{name}: forbidden publication path")
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            errors.append(f"{name}: credential pattern detected (value redacted)")
        if name.endswith(".json"):
            try:
                payload = json.loads(content)
            except (ValueError, UnicodeError):
                errors.append(f"{name}: JSON could not be inspected")
            else:
                if _json_has_credentials(payload):
                    errors.append(f"{name}: credential-bearing JSON field")
        if name == ".env.example":
            for line in content.decode("utf-8").splitlines():
                if "=" not in line or line.lstrip().startswith("#"):
                    continue
                key, value = line.split("=", 1)
                if any(
                    word in key.upper() for word in ("PASSWORD", "SECRET", "TOKEN", "PEPPER")
                ) and not value.startswith("CHANGE_ME"):
                    errors.append(".env.example: credential must be a CHANGE_ME placeholder")
    return errors


def _git_bytes(workspace: Path, arguments: list[str]) -> bytes:
    executable = shutil.which("git")
    if executable is None:
        raise MissingPrerequisiteError("Git is required to inspect the publication payload")
    result = subprocess.run(  # noqa: S603 - fixed Git read-only command
        [executable, *arguments], cwd=workspace, capture_output=True, check=False
    )
    if result.returncode:
        raise MissingPrerequisiteError("Git index could not be inspected; publication is blocked")
    return result.stdout


def publication_check(workspace: Path) -> dict[str, object]:
    names = [
        name.decode("utf-8")
        for name in _git_bytes(workspace, ["ls-files", "-z"]).split(b"\0")
        if name
    ]
    files: dict[str, bytes] = {}
    staged: dict[str, bytes] = {}
    errors = []
    for name in names:
        path = workspace / name
        if (
            path.is_symlink()
            or not path.is_file()
            or not path.resolve().is_relative_to(workspace.resolve())
        ):
            errors.append(f"{name}: missing file or symlink")
            continue
        files[name] = path.read_bytes()
        staged[name] = _git_bytes(workspace, ["show", f":{name}"])
    errors.extend(inspect_payload(files))
    errors.extend(f"staged: {error}" for error in inspect_payload(staged))
    return {
        "safe_payload": not errors,
        "tracked_files": len(names),
        "errors": errors,
        "limitations": [
            "Tracked working tree and staged bytes only; full Git history requires Gitleaks.",
            "Pattern checks do not prove absence of all secrets or application vulnerabilities.",
        ],
    }
