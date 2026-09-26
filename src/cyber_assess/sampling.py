"""Deterministic judgmental sample selection from the PRD."""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class SampleSelection:
    population_count: int
    selected_ids: tuple[str, ...]
    method: str
    seed: int


def select_sample(
    population_ids: Iterable[str], *, seed: int, high_risk_ids: set[str] | None = None
) -> SampleSelection:
    """Test small populations fully; otherwise all exceptions plus ten seeded records."""
    population = list(population_ids)
    if len(set(population)) != len(population):
        raise ValueError("population IDs must be unique")
    if high_risk_ids is None:
        high_risk_ids = set()
    unknown = high_risk_ids.difference(population)
    if unknown:
        raise ValueError(f"high-risk IDs are outside the population: {sorted(unknown)}")
    if len(population) <= 25:
        return SampleSelection(len(population), tuple(population), "complete_population", seed)

    mandatory = [item for item in population if item in high_risk_ids]
    remaining = [item for item in population if item not in high_risk_ids]
    # Determinism is the assurance requirement; this is not a security token.
    random_selection = random.Random(seed).sample(  # noqa: S311
        remaining, min(10, len(remaining))
    )
    selected = tuple(item for item in population if item in set(mandatory + random_selection))
    return SampleSelection(len(population), selected, "judgmental_plus_seeded_random", seed)
