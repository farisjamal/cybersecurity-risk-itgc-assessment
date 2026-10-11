from pathlib import Path
from unittest.mock import patch

import pytest

from cyber_assess.publication import publish_directory


def _sharing_lock() -> PermissionError:
    error = PermissionError("transient Windows sharing lock")
    error.winerror = 32
    return error


def test_transient_windows_lock_retries_atomic_rename(tmp_path: Path) -> None:
    with (
        patch("cyber_assess.publication.os.replace", side_effect=[_sharing_lock(), None]) as rename,
        patch("cyber_assess.publication.time.sleep") as sleep,
    ):
        publish_directory(tmp_path / "staging", tmp_path / "published")
    assert rename.call_count == 2
    sleep.assert_called_once_with(0.1)


def test_persistent_lock_fails_without_copy_fallback(tmp_path: Path) -> None:
    with (
        patch("cyber_assess.publication.os.replace", side_effect=_sharing_lock()) as rename,
        patch("cyber_assess.publication.time.sleep"),
        pytest.raises(PermissionError),
    ):
        publish_directory(tmp_path / "staging", tmp_path / "published")
    assert rename.call_count == 5
    assert not (tmp_path / "published").exists()


def test_existing_publication_is_never_replaced(tmp_path: Path) -> None:
    destination = tmp_path / "published"
    destination.mkdir()
    (destination / "original.txt").write_text("preserve", encoding="utf-8")
    with patch("cyber_assess.publication.os.replace") as rename, pytest.raises(FileExistsError):
        publish_directory(tmp_path / "staging", destination)
    rename.assert_not_called()
    assert (destination / "original.txt").read_text(encoding="utf-8") == "preserve"


def test_non_windows_permission_denial_is_not_retried(tmp_path: Path) -> None:
    with (
        patch(
            "cyber_assess.publication.os.replace", side_effect=PermissionError("denied")
        ) as rename,
        patch("cyber_assess.publication.time.sleep") as sleep,
        pytest.raises(PermissionError),
    ):
        publish_directory(tmp_path / "staging", tmp_path / "published")
    assert rename.call_count == 1
    sleep.assert_not_called()
