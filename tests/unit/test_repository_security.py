from __future__ import annotations

import json
from pathlib import Path

import pytest

from cyber_assess import repository_security
from cyber_assess.repository_security import forbidden_path, inspect_payload, publication_check


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "config/.env",
        ".env.production",
        "config/.env.example",
        "id_ed25519",
        "config/credentials.json",
        "initial-credentials.json",
        "client.pfx",
        "database.sqlite3",
        "backup.sql",
        "debug.har",
        ".aws/credentials",
        "portfolio/report.zip",
        "runtime/token.txt",
    ],
)
def test_sensitive_paths_cannot_enter_publication_payload(path: str) -> None:
    assert forbidden_path(path)


def test_only_placeholder_environment_template_and_shared_ignore_rules_are_allowed() -> None:
    assert not inspect_payload(
        {
            ".gitignore": b".env\nruntime/\n",
            ".env.example": b"POSTGRES_PASSWORD=CHANGE_ME_RANDOM_PASSWORD\n",
        }
    )
    errors = inspect_payload({".env.example": b"POSTGRES_PASSWORD=unsafe-real-looking-value"})
    assert any("shared exclusion" in error for error in errors)
    assert any("CHANGE_ME" in error for error in errors)


def test_secret_findings_redact_values_and_reject_nested_json_credentials() -> None:
    token = "ghp_" + "A" * 40
    errors = inspect_payload(
        {
            ".gitignore": b".env\n",
            "settings.py": token.encode(),
            "fixture.json": json.dumps({"nested": [{"totp_secret": "sensitive"}]}).encode(),
        }
    )
    assert any("settings.py" in error and "redacted" in error for error in errors)
    assert any("credential-bearing JSON" in error for error in errors)
    assert all(token not in error and "sensitive" not in error for error in errors)


def test_staged_secret_cannot_hide_behind_a_clean_working_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    responses = {
        ("ls-files", "-z"): b".gitignore\0settings.json\0",
        ("show", ":.gitignore"): b".env\n",
        ("show", ":settings.json"): b'{"client_secret":"synthetic-test-value"}',
    }
    monkeypatch.setattr(
        repository_security, "_git_bytes", lambda _root, args: responses[tuple(args)]
    )
    result = publication_check(tmp_path)
    assert result["safe_payload"] is False
    assert any(error.startswith("staged:") for error in result["errors"])
