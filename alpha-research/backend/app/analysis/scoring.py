"""The 0-100 stock scoring methodology.

This module defines the category weights and turns per-category ratings into
a total. It does not decide the ratings themselves; those come from separate
analysis steps that are not implemented yet.
"""

from collections.abc import Mapping
from dataclasses import dataclass

METHODOLOGY_VERSION = "1.0"


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    weight: float


CATEGORIES: tuple[Category, ...] = (
    Category("fundamentals", "Fundamental strength", 20),
    Category("valuation", "Valuation attractiveness", 20),
    Category("technical", "Technical structure", 15),
    Category("growth", "Revenue and earnings growth", 15),
    Category("catalysts", "Upcoming catalysts", 10),
    Category("institutional", "Institutional and insider activity", 5),
    Category("industry", "Industry positioning", 5),
    Category("risk_reward", "Risk/reward", 10),
)

# (minimum score, label), checked from the top down.
BANDS: tuple[tuple[int, str], ...] = (
    (90, "Exceptional research candidate"),
    (80, "Very attractive candidate"),
    (70, "Attractive candidate"),
    (60, "Mixed opportunity"),
    (50, "Weak opportunity"),
    (0, "Avoid or deprioritize"),
)

_WEIGHTS = {category.key: category.weight for category in CATEGORIES}
assert sum(_WEIGHTS.values()) == 100


def total_score(ratings: Mapping[str, float]) -> tuple[float, dict[str, float]]:
    """Combine per-category ratings (each 0.0-1.0) into a 0-100 score.

    Every category must be rated. A missing rating is an error rather than an
    implicit zero, so incomplete analysis cannot silently produce a score.
    Returns the total and the points awarded per category.
    """
    missing = set(_WEIGHTS) - set(ratings)
    unknown = set(ratings) - set(_WEIGHTS)
    if missing:
        raise ValueError(f"missing category ratings: {sorted(missing)}")
    if unknown:
        raise ValueError(f"unknown categories: {sorted(unknown)}")

    points: dict[str, float] = {}
    for key, rating in ratings.items():
        if not 0.0 <= rating <= 1.0:
            raise ValueError(f"rating for {key!r} must be between 0 and 1, got {rating}")
        points[key] = round(rating * _WEIGHTS[key], 2)
    return round(sum(points.values()), 2), points


def interpret(score: float) -> str:
    if not 0 <= score <= 100:
        raise ValueError("score must be between 0 and 100")
    for minimum, label in BANDS:
        if score >= minimum:
            return label
    raise AssertionError("unreachable")
