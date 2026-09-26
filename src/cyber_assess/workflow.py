"""Guarded finding lifecycle transitions."""

from __future__ import annotations

from datetime import UTC, datetime

from cyber_assess.models import Finding, FindingStatus, Retest


class InvalidTransitionError(ValueError):
    """Requested finding transition violates the lifecycle."""


_ALLOWED: dict[str, set[str]] = {
    "draft": {"reviewed"},
    "reviewed": {"open"},
    "open": {"in_progress", "risk_accepted", "duplicate"},
    "in_progress": {"ready_for_retest", "risk_accepted"},
    "ready_for_retest": {"closed_verified", "in_progress"},
    "closed_verified": set(),
    "risk_accepted": {"in_progress"},
    "duplicate": set(),
}


def transition_finding(
    finding: Finding,
    requested_status: FindingStatus,
    *,
    retest: Retest | None = None,
    at: datetime | None = None,
) -> Finding:
    """Apply the lifecycle, reopening automatically when a closure retest fails."""
    target: FindingStatus = requested_status
    if requested_status == "closed_verified":
        if retest is None or retest.finding_id != finding.id:
            raise InvalidTransitionError("closed_verified requires an accepted fresh retest")
        if retest.result == "failed":
            target = "in_progress"
        elif not retest.fresh_evidence or retest.decision != "accept_closure":
            raise InvalidTransitionError("closed_verified requires an accepted fresh retest")

    if target not in _ALLOWED[finding.status]:
        raise InvalidTransitionError(f"transition {finding.status} -> {target} is not allowed")
    updates: dict[str, object] = {"status": target}
    if target == "closed_verified":
        updates["closed_at"] = at or datetime.now(UTC)
    return finding.model_copy(update=updates)
