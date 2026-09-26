"""Project-defined 5 x 5 risk scoring."""

from dataclasses import dataclass
from enum import StrEnum


class RiskBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class RiskRating:
    likelihood: int
    impact: int
    score: int
    band: RiskBand


def calculate_risk(likelihood: int, impact: int) -> RiskRating:
    """Return the exact PRD score and band for 1-5 anchors."""
    if not 1 <= likelihood <= 5 or not 1 <= impact <= 5:
        raise ValueError("likelihood and impact must each be between 1 and 5")
    score = likelihood * impact
    if score <= 4:
        band = RiskBand.LOW
    elif score <= 9:
        band = RiskBand.MEDIUM
    elif score <= 16:
        band = RiskBand.HIGH
    else:
        band = RiskBand.CRITICAL
    return RiskRating(likelihood, impact, score, band)
