"""Atomic directory publication with bounded Windows sharing-lock retries."""

from __future__ import annotations

import os
import time
from pathlib import Path


def publish_directory(source: Path, destination: Path) -> None:
    """Keep atomic rename semantics; never fall back to a partially visible copy."""
    for attempt in range(5):
        if destination.exists():
            raise FileExistsError(f"publication already exists: {destination}")
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            # OneDrive/antivirus can briefly hold newly written directories open.
            # Other errors and persistent denials remain failures.
            if getattr(exc, "winerror", None) not in {5, 32} or attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))
